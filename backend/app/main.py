from __future__ import annotations

import hashlib
import json
import os
import random
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional at runtime
    OpenAI = None


MESSAGE_COST = 25
CREDITS_PER_PURCHASE = 1000
MONAD_PRICE = "1 MON"
SHARED_CONTRACT_PATH = Path("/shared/monad-match-credits.json")
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "monad_match.db"
DB_PATH = Path(os.getenv("APP_DB_PATH", str(DEFAULT_DB_PATH)))
LOCAL_RPC_URL = os.getenv("LOCAL_RPC_URL", "http://monad-contracts:8545")
LOCAL_CHAIN_ID = "0x7a6a"
PURCHASE_METHOD_SELECTOR = "0x62c4b64e"
MONAD_PURCHASE_WEI = 10**18
DEV_FAUCET_AMOUNT_WEI = 5 * 10**18


class ConnectWalletRequest(BaseModel):
    wallet_address: str = Field(min_length=4)


class UpdateSelfGenderRequest(BaseModel):
    wallet_address: str
    self_gender: str


class UpdateUserProfileRequest(BaseModel):
    wallet_address: str
    interests: list[str] = Field(default_factory=list)
    bio: str = Field(default="", max_length=280)


class SwipeRequest(BaseModel):
    wallet_address: str
    profile_id: str
    direction: str


class SendMessageRequest(BaseModel):
    wallet_address: str
    message: str = Field(min_length=1, max_length=1000)
    tx_hash: str | None = None


class DemoTopUpRequest(BaseModel):
    wallet_address: str
    credits: int = Field(default=CREDITS_PER_PURCHASE, ge=25, le=10000)


class ClaimCreditsRequest(BaseModel):
    wallet_address: str
    tx_hash: str = Field(min_length=10)


class ChatSignatureRequest(BaseModel):
    wallet_address: str
    signature: str = Field(min_length=10)
    signed_message: str = Field(min_length=10)


class ChatMessage(BaseModel):
    id: str
    sender: str
    kind: str = "text"
    text: str | None = None
    image_url: str | None = None
    tx_hash: str | None = None


class Persona(BaseModel):
    id: str
    name: str
    age: int
    city: str
    tagline: str
    about: str
    traits: list[str]
    interests: list[str]
    green_flags: list[str]
    photo_url: str
    gallery: list[str]
    opener: str
    speech_style: str


class ChatThread(BaseModel):
    id: str
    wallet_address: str
    profile_id: str
    matched: bool = True
    created_at: float = Field(default_factory=time.time)
    messages: list[ChatMessage] = Field(default_factory=list)
    onchain_receipts: list[str] = Field(default_factory=list)
    signature: str | None = None
    signed_message: str | None = None


class WalletSession(BaseModel):
    wallet_address: str
    credits: int = 250
    self_gender: str = "erkek"
    interests: list[str] = Field(default_factory=list)
    bio: str = ""
    chat_ids: list[str] = Field(default_factory=list)


PERSONAS: list[Persona] = [
    Persona(
        id="lina-night-runner",
        name="Lina",
        age=24,
        city="Istanbul",
        tagline="Gece kosulari, synth-pop tutkusu ve dobra flort.",
        about="Gece kosulari, hindistan cevizli soguk kahve ve biraz kaotik muze bulusmalarini severim. Laf sokana laf sokabilen insanlardan hoslanirim.",
        traits=["sportif", "oyuncu", "ozguvenli", "dogrudan"],
        interests=["gece kosulari", "sanat muzeleri", "synth-pop", "matcha"],
        green_flags=["hazir cevap", "hirs", "iyi muzik zevki"],
        photo_url="https://randomuser.me/api/portraits/women/44.jpg",
        gallery=[
            "https://randomuser.me/api/portraits/women/44.jpg",
            "https://randomuser.me/api/portraits/women/45.jpg",
            "https://randomuser.me/api/portraits/women/46.jpg",
        ],
        opener="Gercekten ilginc biri misin, yoksa sadece profil fotografinda mi iyisin?",
        speech_style="flortoz, hizli, zeki ve biraz meydan okuyan",
    ),
    Persona(
        id="deniz-book-coder",
        name="Deniz",
        age=27,
        city="Izmir",
        tagline="Frontend muhendisi, siir kafasi ve tatli bir kaos.",
        about="Gunduz kod yazarim, gece romanlarin altini cizerim. Vapur yolculuklarini ve yagmurlu camlari romantik bulurum.",
        traits=["zeki", "yumusak", "gozlemci", "romantik"],
        interests=["kitaplar", "frontend", "deniz manzarali kafeler", "film muzikleri"],
        green_flags=["nezaket", "istikrar", "merak"],
        photo_url="https://randomuser.me/api/portraits/women/32.jpg",
        gallery=[
            "https://randomuser.me/api/portraits/women/32.jpg",
            "https://randomuser.me/api/portraits/women/33.jpg",
        ],
        opener="Sana kendini canli hissettiren o garip ama cok spesifik seyi anlatsana.",
        speech_style="sicak, dusunceli, siirsel ve ilk basta biraz utangac",
    ),
    Persona(
        id="arya-founder-mode",
        name="Arya",
        age=26,
        city="Ankara",
        tagline="Startup enerjisi, spor disiplini, gozu hep siradaki buyuk iste.",
        about="Kahvaltidan once cesur fikirler satarim, yine de gece doner kacamaklarina vakit ayiririm.",
        traits=["hirsli", "rekabetci", "karizmatik", "yuksek enerjili"],
        interests=["startup'lar", "agirlik antrenmani", "kripto", "yolculuklar"],
        green_flags=["ozguven", "mizah", "kararlilik"],
        photo_url="https://randomuser.me/api/portraits/women/68.jpg",
        gallery=[
            "https://randomuser.me/api/portraits/women/68.jpg",
            "https://randomuser.me/api/portraits/women/69.jpg",
        ],
        opener="Ilk bulusmamizi bana seed turu sunuyormus gibi anlat.",
        speech_style="iddiali, net, enerjik ve hafif ukala",
    ),
    Persona(
        id="maya-camera-soul",
        name="Maya",
        age=23,
        city="Bodrum",
        tagline="Film ceker, gun batimini kovalar, tehlikeli sorular sorar.",
        about="Yarim kalmis gunlukler, eski kameralar ve yabancilarin fark etmeden anlattigi hikayeleri biriktiririm.",
        traits=["sanatsal", "yogun", "merakli", "cekici"],
        interests=["analog fotografcilik", "sahil yuruyusleri", "jazz barlari", "vintage alisveris"],
        green_flags=["duygusal zeka", "zevk sahibi olmak", "spontanelik"],
        photo_url="https://randomuser.me/api/portraits/women/52.jpg",
        gallery=[
            "https://randomuser.me/api/portraits/women/52.jpg",
            "https://randomuser.me/api/portraits/women/53.jpg",
        ],
        opener="Sende insanlarin genelde cok gec fark ettigi sey ne?",
        speech_style="duygulu, derin, sinematik",
    ),
    Persona(
        id="selin-chaotic-good",
        name="Selin",
        age=25,
        city="Eskisehir",
        tagline="Yari zamanli DJ, tam zamanli tatli bela.",
        about="Kapsonunu da patatesini de calmam cok olasi. Sıkıcıysan bunu 90 saniyede anlarim.",
        traits=["komik", "kaotik", "takilan", "sosyal"],
        interests=["DJ setleri", "sokak lezzetleri", "festivaller", "mizah"],
        green_flags=["laflasma", "enerji", "maceracilik"],
        photo_url="https://randomuser.me/api/portraits/women/12.jpg",
        gallery=[
            "https://randomuser.me/api/portraits/women/12.jpg",
            "https://randomuser.me/api/portraits/women/13.jpg",
        ],
        opener="Onemli uyum testi: tatliyi paylasir misin yoksa savas mi cikarirsin?",
        speech_style="komik, arsiz, internet dili bilen, hizli",
    ),
    Persona(
        id="ece-surf-lawyer",
        name="Ece",
        age=28,
        city="Cesme",
        tagline="Hafta ici plaza, gun dogarken sörf tahtasi.",
        about="Cuma sozlesme kapatirim, cumartesi sabahi kiyida kaybolurum. Sakin ozguvenden hoslanirim.",
        traits=["zeki", "sakin", "atletik", "secici"],
        interests=["sörf", "hukuk", "gun dogumu yuruyusleri", "minimal stil"],
        green_flags=["netlik", "ozsaygi", "duygusal denge"],
        photo_url="https://randomuser.me/api/portraits/women/24.jpg",
        gallery=[
            "https://randomuser.me/api/portraits/women/24.jpg",
            "https://randomuser.me/api/portraits/women/25.jpg",
        ],
        opener="Pahali olmasa da sana pahali hissettiren hayat nasil bir sey?",
        speech_style="sade, zarif, keskin, dramasiz",
    ),
    Persona(
        id="naz-ceramic-heart",
        name="Naz",
        age=24,
        city="Canakkale",
        tagline="Seramik yapar, playlist yakar, goz temasini fazla dusunur.",
        about="Rahat hissedene kadar yumusagim, sonra bir anda komik ve susmak bilmeyen birine donusurum.",
        traits=["nazik", "yaratici", "tatli sakar", "sadik"],
        interests=["seramik", "indie playlistler", "kucuk kitapcilar", "kediler"],
        green_flags=["sabir", "yumusak mizah", "sevgi gosterebilmek"],
        photo_url="https://randomuser.me/api/portraits/women/16.jpg",
        gallery=[
            "https://randomuser.me/api/portraits/women/16.jpg",
            "https://randomuser.me/api/portraits/women/17.jpg",
        ],
        opener="Dürüst ol, aska yavas yavas mi dusersin yoksa bir anda mi?",
        speech_style="yumusak, samimi, biraz utangac, tatli",
    ),
    Persona(
        id="irem-flight-mode",
        name="Irem",
        age=29,
        city="Antalya",
        tagline="Kabin memuru enerjisi, dolu pasaport, kisitli sabir.",
        about="Bir sehirden ayrilmanin bes yolunu bilirim; kalmanin ise tek bir nedeni vardir: sohbet gercekten degiyorsa.",
        traits=["dunya gormus", "cekici", "yerinde duramayan", "iddiali"],
        interests=["seyahat", "havaalanlari", "beach club'lar", "gec aksam yemekleri"],
        green_flags=["uyum saglayabilmek", "mizah", "kimya"],
        photo_url="https://randomuser.me/api/portraits/women/72.jpg",
        gallery=[
            "https://randomuser.me/api/portraits/women/72.jpg",
            "https://randomuser.me/api/portraits/women/73.jpg",
        ],
        opener="Hayatini gercekten daha iyi yapan en plansiz hareketin neydi?",
        speech_style="akici, ozguvenli, takilan, dunya gormus",
    ),
    Persona(
        id="zeynep-astro-architect",
        name="Zeynep",
        age=27,
        city="Bursa",
        tagline="Bina tasarlar, eglencesine dogum haritasi okur, isiga acimasiz davranir.",
        about="Bir mekanin akustigi kotu, kahvesi daha da kotuyse hemen anlarim. Flort etmeyi tuhaf derecede derin sorular sorarak yaparim.",
        traits=["analitik", "sik", "gizemli", "titiz"],
        interests=["mimari", "astroloji", "nitelikli kahve", "ic mekan tasarimi"],
        green_flags=["zevk sahibi olmak", "istikrar", "derinlik"],
        photo_url="https://randomuser.me/api/portraits/women/36.jpg",
        gallery=[
            "https://randomuser.me/api/portraits/women/36.jpg",
            "https://randomuser.me/api/portraits/women/37.jpg",
        ],
        opener="Sence kimya insa mi edilir, kesfedilir mi, yoksa her sey kotu zamanlama mi?",
        speech_style="dusunceli, stil sahibi, hafif entelektuel takilan",
    ),
    Persona(
        id="asli-boxing-brunch",
        name="Asli",
        age=26,
        city="Adana",
        tagline="Sabah 7'de yumruk atar, yine de brunch'ta senden iyi gorunur.",
        about="Disiplin, yuksek kahkaha ve kendini gostermeye calismadan ayak uydurabilen insanlari severim.",
        traits=["disiplinli", "ozguvenli", "koruyucu", "eglenceli"],
        interests=["boks", "brunch", "sokak stili", "hafta sonu kacamaklari"],
        green_flags=["guc", "durustluk", "oyunculuk"],
        photo_url="https://randomuser.me/api/portraits/women/60.jpg",
        gallery=[
            "https://randomuser.me/api/portraits/women/60.jpg",
            "https://randomuser.me/api/portraits/women/61.jpg",
        ],
        opener="Cesur gorundugun icin mi cesursun, yoksa o ifadeyi iyi mi calistin?",
        speech_style="dogrudan, enerjik, ayagi yere basan",
    ),
    Persona(
        id="damla-gamer-lawless",
        name="Damla",
        age=23,
        city="Samsun",
        tagline="Ranked gamer, kapson hirsizi, ileri seviye sesli mesaj bagimlisi.",
        about="Alti saat araliksiz odaklanabilirim ama yine de siradan gunleri eglenceli hissettirecek birini isterim.",
        traits=["komik", "rekabetci", "sicak", "tatli yapiskan"],
        interests=["oyunlar", "gece atistirmaliklari", "sesli mesajlar", "anime"],
        green_flags=["ilgi gostermek", "laflasma", "koruyucu enerji"],
        photo_url="https://randomuser.me/api/portraits/women/20.jpg",
        gallery=[
            "https://randomuser.me/api/portraits/women/20.jpg",
            "https://randomuser.me/api/portraits/women/21.jpg",
        ],
        opener="Ciddi soru: biz duo girecek kadar uyumlu muyuz, yoksa oyunlarimi satacak misin?",
        speech_style="oyuncu, internet dili bilen, sicak, hafif sahiplenen",
    ),
    Persona(
        id="melis-michelin-chaos",
        name="Melis",
        age=30,
        city="Istanbul",
        tagline="Asci elleri, tehlikeli bakislar, kusursuz risotto enerjisi.",
        about="Sevdigim insanlari doyururum. Sevmediklerimden kaybolurum. Sistem gayet basit aslinda.",
        traits=["cekici", "becerikli", "degisken ruhlu", "manyetik"],
        interests=["yemek yapmak", "sarap barlari", "uretici pazarlar", "jazz"],
        green_flags=["zevk", "ozguven", "baglilik"],
        photo_url="https://randomuser.me/api/portraits/women/54.jpg",
        gallery=[
            "https://randomuser.me/api/portraits/women/54.jpg",
            "https://randomuser.me/api/portraits/women/55.jpg",
        ],
        opener="Ucuncu bulusmada sana yemek yapsam bunu romantizm mi sayarsin, strateji mi?",
        speech_style="yavas, etkileyici, keskin, niyetli",
    ),
    Persona(
        id="yagmur-hackathon-girl",
        name="Yagmur",
        age=25,
        city="Kocaeli",
        tagline="Hackathon, bubble tea ve supheli derecede kusursuz eyeliner.",
        about="Saatlerce urun fikri konusabilirim, sonra sacma sapan bir sticker paketine duygusal bag kurarim.",
        traits=["parlak", "zeki", "hirsli", "civiltli"],
        interests=["hackathon'lar", "AI araclari", "bubble tea", "sticker'lar"],
        green_flags=["heves", "odak", "sicaklik"],
        photo_url="https://randomuser.me/api/portraits/women/28.jpg",
        gallery=[
            "https://randomuser.me/api/portraits/women/28.jpg",
            "https://randomuser.me/api/portraits/women/29.jpg",
        ],
        opener="En acayip startup fikrini anlat. Ilk ben gulmeyecegime soz veriyorum.",
        speech_style="hizli, zeki, hevesli, internet dili bilen",
    ),
    Persona(
        id="bera-yacht-poise",
        name="Bera",
        age=29,
        city="Mugla",
        tagline="Pahali gorunur, yuksek sesle guler, sacma esprilere gizlice bayilir.",
        about="Insanlar beni mesafeli sanar ama odadaki herkes hakkinda absurt gozlemler yapmaya baslayinca fikirleri degisir.",
        traits=["zarif", "komik", "gozlemci", "standardi yuksek"],
        interests=["yelken", "moda", "deniz urunlu aksam yemekleri", "insan izlemek"],
        green_flags=["ozguven", "nezaket", "mizah"],
        photo_url="https://randomuser.me/api/portraits/women/62.jpg",
        gallery=[
            "https://randomuser.me/api/portraits/women/62.jpg",
            "https://randomuser.me/api/portraits/women/63.jpg",
        ],
        opener="Guzel seyleri ve daha da guzel sohbetleri seven biriyle ayak uydurabilir misin?",
        speech_style="parlak, esprituel, sosyal olarak akici",
    ),
    Persona(
        id="ceyda-music-therapy",
        name="Ceyda",
        age=28,
        city="Mersin",
        tagline="Terapist kafasi, kadife ses, insanlari yavas yavas bitiren playlistler.",
        about="Kelimelerden once tonu fark ederim. Duygusal olarak orada olabilen ama bunu TED konusmasina cevirmeyen erkekleri severim.",
        traits=["empatik", "yakın", "sakin", "cekici"],
        interests=["psikoloji", "canli muzik", "deniz esintisi", "yavas sabahlar"],
        green_flags=["kendini taniyor olmak", "sefkat", "mizah"],
        photo_url="https://randomuser.me/api/portraits/women/40.jpg",
        gallery=[
            "https://randomuser.me/api/portraits/women/40.jpg",
            "https://randomuser.me/api/portraits/women/41.jpg",
        ],
        opener="Bir insanda seni aninda guvende hissettiren kucuk sey ne?",
        speech_style="sicak, yakin, duygusal olarak zeki",
    ),
    Persona(
        id="sude-afterparty-runclub",
        name="Sude",
        age=24,
        city="Izmir",
        tagline="After party yuzu, kosu kulubu cigeri, imkansiz celiskiler.",
        about="Dayanikli bir flort isterim. Enerjime yetis ya da en azindan ona hayran kal.",
        traits=["elektrik gibi", "sosyal", "vahsi", "disiplinli"],
        interests=["kosu kulubu", "tekno geceleri", "pilates", "sahil gunleri"],
        green_flags=["ozguven", "enerji", "inisiyatif"],
        photo_url="https://randomuser.me/api/portraits/women/48.jpg",
        gallery=[
            "https://randomuser.me/api/portraits/women/48.jpg",
            "https://randomuser.me/api/portraits/women/49.jpg",
        ],
        opener="Durust ol, benim takvimimde bir hafta sonu cikarabilir misin?",
        speech_style="hizli, flortoz, enerjik, biraz tehlikeli",
    ),
    Persona(
        id="kaan-iron-smile",
        name="Kaan",
        age=29,
        city="İstanbul",
        tagline="Gömlek içinde sakin, salonda ağır ve omuzları gerçekten çok geniş.",
        about="Sabah ağırlık, akşam iyi kahve. Güven veren ama çekici kalan dengeyi seviyorum.",
        traits=["kaslı", "özgüvenli", "korumacı", "sakin"],
        interests=["fitness", "box fit", "özel kahveciler", "boğaz yürüyüşleri"],
        green_flags=["istikrar", "netlik", "öz bakım"],
        photo_url="https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=1200&h=1600&q=85",
        gallery=[
            "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1504593811423-6dd665756598?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
        opener="Profiline baktım, ama ben enerjiyi fotoğraftan çok bakıştan okurum. Sende o bakış var mı?",
        speech_style="rahat, çekici, net ve hafif flörtöz",
    ),
    Persona(
        id="emir-night-lift",
        name="Emir",
        age=27,
        city="İzmir",
        tagline="Gündüz kreatif direktör, gece spor salonunun en düzenli kaosu.",
        about="Bakımlı olmakla fazla kasıntı olmak arasında ince bir çizgi var. Ben ilkini seviyorum.",
        traits=["kaslı", "stil sahibi", "güler yüzlü", "iddialı"],
        interests=["bodybuilding", "street style", "sahil koşusu", "kokteyl"],
        green_flags=["özen", "mizah", "maskülen enerji"],
        photo_url="https://images.unsplash.com/photo-1504593811423-6dd665756598?auto=format&fit=crop&w=1200&h=1600&q=85",
        gallery=[
            "https://images.unsplash.com/photo-1504593811423-6dd665756598?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
        opener="Biraz yüksek standartlıyım, o yüzden direkt sorayım: dikkat çeken tarafın tavrın mı fiziğin mi?",
        speech_style="özgüvenli, modern, direkt ve oyunbaz",
    ),
    Persona(
        id="atlas-coastline",
        name="Atlas",
        age=30,
        city="Antalya",
        tagline="Bronz ten, geniş sırt, beach club yerine sakin koy seven adam.",
        about="Kas gösteriş için değil disiplin için güzel. Ama iyi görünmenin keyfini inkâr edecek kadar da mütevazı değilim.",
        traits=["kaslı", "esmer", "sakin", "karizmatik"],
        interests=["yüzme", "fonksiyonel antrenman", "tekne kaçamakları", "ızgara yemek"],
        green_flags=["güven", "denge", "koruyucu tavır"],
        photo_url="https://images.unsplash.com/photo-1504257432389-52343af06ae3?auto=format&fit=crop&w=1200&h=1600&q=85",
        gallery=[
            "https://images.unsplash.com/photo-1504257432389-52343af06ae3?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
        opener="Bende çekim genelde sessiz başlar. Sen daha çok sakin tehlike misin, yüksek enerji mi?",
        speech_style="yavaş, derin, maskülen ve kontrollü",
    ),
    Persona(
        id="mert-rack-focus",
        name="Mert",
        age=28,
        city="Ankara",
        tagline="Omuzlar salon işi, zekâ aileden, flört ise tamamen kişisel başarı.",
        about="Düzgün cümle kurabilen, iyi giyinen ve formuna bakan erkek hâlâ çok nadir. Ben o nadir taraftayım.",
        traits=["kaslı", "zeki", "bakımlı", "rekabetçi"],
        interests=["powerlifting", "saatler", "iyi restoranlar", "uzun araba sürüşü"],
        green_flags=["kararlılık", "denge", "yakışıklı özgüven"],
        photo_url="https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?auto=format&fit=crop&w=1200&h=1600&q=85",
        gallery=[
            "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1504593811423-6dd665756598?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
        opener="Benimle eşleşen biri ya çok meraklıdır ya da risk almayı seviyordur. Sen hangisisin?",
        speech_style="kendinden emin, akıllı, hafif dominant",
    ),
    Persona(
        id="baran-marina-frame",
        name="Baran",
        age=31,
        city="Muğla",
        tagline="Marina ışığı, geniş göğüs, pahalı görünmeden pahalı hissettiren enerji.",
        about="Form, koku ve bakış üçlüsüne inanırım. Kimyada bunlar ilk üç saniyede belli oluyor zaten.",
        traits=["kaslı", "şık", "sosyal", "çekici"],
        interests=["yat kulübü", "crossfit", "akşam yemeği", "hafta sonu otelleri"],
        green_flags=["özgüven", "cömertlik", "sahiplenici sıcaklık"],
        photo_url="https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=1200&h=1600&q=85",
        gallery=[
            "https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1504257432389-52343af06ae3?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
        opener="İlk izlenimde bana bakıp 'tehlikeli ama değer' diyor musun, yoksa daha mı temkinlisin?",
        speech_style="parlak, erkeksi, akıcı ve flörtte rahat",
    ),
    Persona(
        id="arda-studio-cut",
        name="Arda",
        age=26,
        city="Bursa",
        tagline="Geniş kollar, temiz yüz hattı, biraz da sanat okulundan kalma çekicilik.",
        about="Kaslı olmak kaba olmak demek değil. Ben biraz estetik, biraz disiplin, biraz da göz temasıyım.",
        traits=["kaslı", "estetik", "nazik", "çekim gücü yüksek"],
        interests=["hypertrophy", "tasarım", "fotoğraf", "hafta içi akşam sporları"],
        green_flags=["ince düşünce", "bedenine özen", "yüksek çekim"],
        photo_url="https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=1200&h=1600&q=85",
        gallery=[
            "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1504257432389-52343af06ae3?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1504593811423-6dd665756598?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
        opener="Sence çekicilik daha çok görüntü mü, tavır mı? Benim cevabım ikisinin iyi oranı.",
        speech_style="tatlı sert, estetik, rahat ve cilalı",
    ),
]

PROFILE_DETAILS: dict[str, dict[str, Any]] = {
    "lina-night-runner": {
        "profession": "Marka Stratejisti",
        "education": "Galatasaray Universitesi",
        "looking_for": "Flort, kimya ve yuksek enerjili bir bag",
        "weekend_plan": "Sabah kosusu, oglen kahve, aksam sergi ya da kokteyl",
        "ideal_date": "Muze + uzun yuruyus + plansiz ikinci mekan",
        "neighborhoods": ["Cihangir", "Karakoy", "Moda"],
        "deal_breakers": ["pasiflik", "kotu mizah", "mesajlasmada ruhsuzluk"],
    },
    "deniz-book-coder": {
        "profession": "Frontend Developer",
        "education": "Ege Universitesi",
        "looking_for": "Yavas acilan ama derin bir bag",
        "weekend_plan": "Kitapci gezmek, sahilde kahve icmek, aksam sakin bir bar",
        "ideal_date": "Vapur yolculugu ve uzun sohbet",
        "neighborhoods": ["Alsancak", "Karatas", "Bostanli"],
        "deal_breakers": ["sertlik", "sabirsizlik", "yuzeysel konusma"],
    },
    "arya-founder-mode": {
        "profession": "Startup Kurucusu",
        "education": "Bilkent Isletme",
        "looking_for": "Tutku, tempo ve guclu partner enerjisi",
        "weekend_plan": "Antrenman, networking brunch, gece spontane kacamak",
        "ideal_date": "Rekabetli bir aktivite ve iyi yemek",
        "neighborhoods": ["Cankaya", "Beytepe", "Mesa"],
        "deal_breakers": ["kararsizlik", "hedefsizlik", "dusuk enerji"],
    },
    "maya-camera-soul": {
        "profession": "Fotografci",
        "education": "Mimar Sinan Guzel Sanatlar",
        "looking_for": "Derin kimya ve gizemli bir cekim",
        "weekend_plan": "Plaj yuruyusu, analog cekim, gece jazz",
        "ideal_date": "Gun batimi ve uzun bakislar",
        "neighborhoods": ["Yalikavak", "Gumusluk", "Bitez"],
        "deal_breakers": ["sikicilik", "duygusal kapalilik", "kaba enerji"],
    },
    "selin-chaotic-good": {
        "profession": "DJ / Etkinlik Kuratoru",
        "education": "Anadolu Iletisim",
        "looking_for": "Yuksek enerji, guclu mizah ve kaosu tasiyabilecek biri",
        "weekend_plan": "Street food, festival, after party",
        "ideal_date": "Canli muzik + tatli kapisma",
        "neighborhoods": ["Adalar", "Doktorlar", "Baglar"],
        "deal_breakers": ["sikicilik", "trip", "kendini fazla onemseme"],
    },
    "ece-surf-lawyer": {
        "profession": "Avukat",
        "education": "Koc Hukuk",
        "looking_for": "Olgun, sakin, ozguvenli bir eslesme",
        "weekend_plan": "Sabah surf, gun icinde beach lunch, aksam sarap",
        "ideal_date": "Gun dogumu ve deniz kenari kahve",
        "neighborhoods": ["Alacati", "Ilica", "Pasalimani"],
        "deal_breakers": ["drama", "saygisizlik", "ozensizlik"],
    },
    "naz-ceramic-heart": {
        "profession": "Seramik Sanatcisi",
        "education": "Canakkale Onsekiz Mart GSF",
        "looking_for": "Nazik ama gercek bir yakinlik",
        "weekend_plan": "Atolye, ikinci el kitapci, sakin kahve",
        "ideal_date": "Kucuk bir sanat atolyesi ve sokak yuruyusu",
        "neighborhoods": ["Merkez", "Kordon", "Bozcaada kacamagi"],
        "deal_breakers": ["kabalik", "sabirsizlik", "duygusal sogukluk"],
    },
    "irem-flight-mode": {
        "profession": "Kabin Memuru",
        "education": "Turizm ve Otelcilik",
        "looking_for": "Spontane ama guven veren bir bag",
        "weekend_plan": "Ucaktan inip direkt denize kacmak",
        "ideal_date": "Havaalani hikayeleri ve gece yemegi",
        "neighborhoods": ["Lara", "Kaleici", "Konyaalti"],
        "deal_breakers": ["kisitlayicilik", "kiskanclik krizi", "plansizlikta panik"],
    },
    "zeynep-astro-architect": {
        "profession": "Mimar",
        "education": "ODTU Mimarlik",
        "looking_for": "Estetik anlayisi olan, akli da cekici biri",
        "weekend_plan": "Yeni mekan kesfi, kahve, tasarim magazalari",
        "ideal_date": "Tasarim odakli bir sergi ve iyi kahve",
        "neighborhoods": ["Nilufer", "Gorukle", "Mudanya"],
        "deal_breakers": ["zevksizlik", "ozensizlik", "konusamamak"],
    },
    "asli-boxing-brunch": {
        "profession": "Pilates ve Boks Koçu",
        "education": "Spor Bilimleri",
        "looking_for": "Guc ve yumusakligin dengesi",
        "weekend_plan": "Sabah antrenman, oglen brunch, aksam road trip",
        "ideal_date": "Hareketli bir aktivite ve iyi yemek",
        "neighborhoods": ["Seyhan", "Cukurova", "Ataturk Parki cevresi"],
        "deal_breakers": ["ozensizlik", "bahane uretmek", "kendine bakmamak"],
    },
    "damla-gamer-lawless": {
        "profession": "Streamer / Topluluk Yoneticisi",
        "education": "Bilgisayar Programciligi",
        "looking_for": "Eglenceli, sahiplenen ve online-offline dengeli biri",
        "weekend_plan": "Duo queue, gece atistirma, sabaha karsi sesli mesaj",
        "ideal_date": "Arcade + ramen + uzun voice note",
        "neighborhoods": ["Atakum", "Sahil", "Kampus cevresi"],
        "deal_breakers": ["ghostlamak", "asiri ego", "iletisimsizlik"],
    },
    "melis-michelin-chaos": {
        "profession": "Ozel Davet Shefi",
        "education": "Le Cordon Bleu sertifika programi",
        "looking_for": "Tutkulu ama zarif bir bag",
        "weekend_plan": "Pazar alisverisi, yemek denemesi, jazz bar",
        "ideal_date": "Birlikte yemek tadimi ve gece yuruyusu",
        "neighborhoods": ["Nisantasi", "Arnavutkoy", "Bebek"],
        "deal_breakers": ["zevksizlik", "oyle gelmesi", "cabasizlik"],
    },
    "yagmur-hackathon-girl": {
        "profession": "Product Designer",
        "education": "ITU Endustri Urunleri Tasarimi",
        "looking_for": "Hem zeki hem sicak bir enerji",
        "weekend_plan": "Hackathon, bubble tea, sahilde fikir konusmak",
        "ideal_date": "Konsept kafe + gelecegi kurtaran fikirler",
        "neighborhoods": ["Basiskele", "Izmit Merkez", "Yahya Kaptan"],
        "deal_breakers": ["negatiflik", "meraksizlik", "soguk tavir"],
    },
    "bera-yacht-poise": {
        "profession": "Luks Etkinlik Danismani",
        "education": "Bosphorus Tourism School",
        "looking_for": "Kendine guvenen ve masaya enerji koyan biri",
        "weekend_plan": "Tekne, uzun aksam yemegi, absurt espriler",
        "ideal_date": "Sahil kenari yemek ve iyi sohbet",
        "neighborhoods": ["Gocek", "Akyaka", "Bodrum kacamagi"],
        "deal_breakers": ["nezaketsizlik", "gosteri meraki", "sogukluk"],
    },
    "ceyda-music-therapy": {
        "profession": "Psikolog",
        "education": "Bogazici Psikoloji",
        "looking_for": "Duygusal olgunluk ve huzurlu tutku",
        "weekend_plan": "Canli muzik, deniz, yavas kahvalti",
        "ideal_date": "Canli muzik sonrasi uzun yuruyus",
        "neighborhoods": ["Pozcu", "Marina", "sahil seridi"],
        "deal_breakers": ["duyarsizlik", "empati eksikligi", "oyun oynamak"],
    },
    "sude-afterparty-runclub": {
        "profession": "Sosyal Medya Kreatifi",
        "education": "Dokuz Eylul Medya",
        "looking_for": "Yuksek enerji ve guvenli flort",
        "weekend_plan": "Kosu kulubu, beach, gece techno",
        "ideal_date": "Gunduz spor, gece dans",
        "neighborhoods": ["Alsancak", "Bornova", "Urla kacamagi"],
        "deal_breakers": ["dusuk enerji", "trip", "kararsizlik"],
    },
    "kaan-iron-smile": {
        "profession": "Marka Danışmanı",
        "education": "Boğaziçi Üniversitesi",
        "looking_for": "Yüksek çekim, net enerji ve feminen bir denge",
        "weekend_plan": "Sabah antrenman, öğlen kahve, akşam iyi yemek",
        "ideal_date": "Boğaz yürüyüşü ve uzun göz teması olan bir akşam",
        "neighborhoods": ["Etiler", "Karaköy", "Caddebostan"],
        "deal_breakers": ["bakımsızlık", "kararsızlık", "pasif enerji"],
    },
    "emir-night-lift": {
        "profession": "Kreatif Direktör",
        "education": "Yaşar Üniversitesi",
        "looking_for": "Dişi enerjisi yüksek, sohbeti güçlü bir eşleşme",
        "weekend_plan": "Sahil koşusu, espresso, akşam kokteyl",
        "ideal_date": "Şık ama rahat bir akşam planı",
        "neighborhoods": ["Alaçatı", "Bostanlı", "Alsancak"],
        "deal_breakers": ["özensizlik", "soğukluk", "oyun oynamak"],
    },
    "atlas-coastline": {
        "profession": "Spor Kulübü Ortağı",
        "education": "Akdeniz Spor Bilimleri",
        "looking_for": "Sakin ama yüksek kimyeli bir bağ",
        "weekend_plan": "Deniz, yüzme, gün batımı yemeği",
        "ideal_date": "Koy kaçamağı ve yavaş sohbet",
        "neighborhoods": ["Lara", "Kaş", "Konyaaltı"],
        "deal_breakers": ["drama", "güvensizlik", "fazla ego"],
    },
    "mert-rack-focus": {
        "profession": "Finans Müdürü",
        "education": "ODTÜ İşletme",
        "looking_for": "Zeki, feminen ve standardı yüksek biri",
        "weekend_plan": "Ağırlık antrenmanı, iyi restoran, gece sürüşü",
        "ideal_date": "Şarap ve uzun masa sohbeti",
        "neighborhoods": ["Çankaya", "Bilkent", "İncek"],
        "deal_breakers": ["dağınıklık", "tutarsızlık", "fazla trip"],
    },
    "baran-marina-frame": {
        "profession": "Lüks Turizm Yatırımcısı",
        "education": "İTÜ Denizcilik",
        "looking_for": "Çekim gücü yüksek, bakımlı ve dişi biri",
        "weekend_plan": "Marina, antrenman, akşam yemeği",
        "ideal_date": "Deniz kenarında uzun akşam",
        "neighborhoods": ["Göcek", "Yalıkavak", "Akyaka"],
        "deal_breakers": ["kabalık", "ne istediğini bilmemek", "aşırı kıskançlık"],
    },
    "arda-studio-cut": {
        "profession": "Art Director",
        "education": "Mimar Sinan Güzel Sanatlar",
        "looking_for": "Güzel enerji, estetik zevk ve fiziksel çekim",
        "weekend_plan": "Spor, sergi, kahve ve spontane plan",
        "ideal_date": "Galeri sonrası sakin bar",
        "neighborhoods": ["Nilüfer", "Mudanya", "Özlüce"],
        "deal_breakers": ["ruhsuzluk", "özensizlik", "aşırı sertlik"],
    },
}

PROFILE_MEDIA: dict[str, dict[str, Any]] = {
    "lina-night-runner": {
        "photo_url": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=1200&h=1600&q=85",
        "gallery": [
            "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
    },
    "deniz-book-coder": {
        "photo_url": "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?auto=format&fit=crop&w=1200&h=1600&q=85",
        "gallery": [
            "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1488426862026-3ee34a7d66df?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1487412720507-e7ab37603c6f?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
    },
    "arya-founder-mode": {
        "photo_url": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=1200&h=1600&q=85",
        "gallery": [
            "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1517365830460-955ce3ccd263?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
    },
    "maya-camera-soul": {
        "photo_url": "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=1200&h=1600&q=85",
        "gallery": [
            "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
    },
    "selin-chaotic-good": {
        "photo_url": "https://images.unsplash.com/photo-1488426862026-3ee34a7d66df?auto=format&fit=crop&w=1200&h=1600&q=85",
        "gallery": [
            "https://images.unsplash.com/photo-1488426862026-3ee34a7d66df?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1546961329-78bef0414d7c?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1542204625-de293a2f8ff5?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
    },
    "ece-surf-lawyer": {
        "photo_url": "https://images.unsplash.com/photo-1517365830460-955ce3ccd263?auto=format&fit=crop&w=1200&h=1600&q=85",
        "gallery": [
            "https://images.unsplash.com/photo-1517365830460-955ce3ccd263?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1499952127939-9bbf5af6c51c?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
    },
    "naz-ceramic-heart": {
        "photo_url": "https://images.unsplash.com/photo-1499952127939-9bbf5af6c51c?auto=format&fit=crop&w=1200&h=1600&q=85",
        "gallery": [
            "https://images.unsplash.com/photo-1499952127939-9bbf5af6c51c?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1487412720507-e7ab37603c6f?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
    },
    "irem-flight-mode": {
        "photo_url": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=1200&h=1600&q=85",
        "gallery": [
            "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
    },
    "zeynep-astro-architect": {
        "photo_url": "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?auto=format&fit=crop&w=1200&h=1600&q=85",
        "gallery": [
            "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1517365830460-955ce3ccd263?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
    },
    "asli-boxing-brunch": {
        "photo_url": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=1200&h=1600&q=85",
        "gallery": [
            "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1542204625-de293a2f8ff5?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1546961329-78bef0414d7c?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
    },
    "damla-gamer-lawless": {
        "photo_url": "https://images.unsplash.com/photo-1546961329-78bef0414d7c?auto=format&fit=crop&w=1200&h=1600&q=85",
        "gallery": [
            "https://images.unsplash.com/photo-1546961329-78bef0414d7c?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1481214110143-ed630356e1bb?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1488426862026-3ee34a7d66df?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
    },
    "melis-michelin-chaos": {
        "photo_url": "https://images.unsplash.com/photo-1542204625-de293a2f8ff5?auto=format&fit=crop&w=1200&h=1600&q=85",
        "gallery": [
            "https://images.unsplash.com/photo-1542204625-de293a2f8ff5?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1544005313-94ddf0286df2?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
    },
    "yagmur-hackathon-girl": {
        "photo_url": "https://images.unsplash.com/photo-1481214110143-ed630356e1bb?auto=format&fit=crop&w=1200&h=1600&q=85",
        "gallery": [
            "https://images.unsplash.com/photo-1481214110143-ed630356e1bb?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1499952127939-9bbf5af6c51c?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
    },
    "bera-yacht-poise": {
        "photo_url": "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=1200&h=1600&q=85",
        "gallery": [
            "https://images.unsplash.com/photo-1517841905240-472988babdf9?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1529626455594-4ff0802cfb7e?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
    },
    "ceyda-music-therapy": {
        "photo_url": "https://images.unsplash.com/photo-1487412720507-e7ab37603c6f?auto=format&fit=crop&w=1200&h=1600&q=85",
        "gallery": [
            "https://images.unsplash.com/photo-1487412720507-e7ab37603c6f?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1438761681033-6461ffad8d80?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1499952127939-9bbf5af6c51c?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
    },
    "sude-afterparty-runclub": {
        "photo_url": "https://images.unsplash.com/photo-1545239351-1141bd82e8a6?auto=format&fit=crop&w=1200&h=1600&q=85",
        "gallery": [
            "https://images.unsplash.com/photo-1545239351-1141bd82e8a6?auto=format&fit=crop&w=1200&h=1600&q=85",
            "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=1000&h=1300&q=85",
            "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?auto=format&fit=crop&w=1000&h=1300&q=85",
        ],
    },
}

PERSONA_GENDERS: dict[str, str] = {
    "lina-night-runner": "kadin",
    "deniz-book-coder": "kadin",
    "arya-founder-mode": "kadin",
    "maya-camera-soul": "kadin",
    "selin-chaotic-good": "kadin",
    "ece-surf-lawyer": "kadin",
    "naz-ceramic-heart": "kadin",
    "irem-flight-mode": "kadin",
    "zeynep-astro-architect": "kadin",
    "asli-boxing-brunch": "kadin",
    "damla-gamer-lawless": "kadin",
    "melis-michelin-chaos": "kadin",
    "yagmur-hackathon-girl": "kadin",
    "bera-yacht-poise": "kadin",
    "ceyda-music-therapy": "kadin",
    "sude-afterparty-runclub": "kadin",
    "kaan-iron-smile": "erkek",
    "emir-night-lift": "erkek",
    "atlas-coastline": "erkek",
    "mert-rack-focus": "erkek",
    "baran-marina-frame": "erkek",
    "arda-studio-cut": "erkek",
}

PERSONA_MAP = {persona.id: persona for persona in PERSONAS}
SESSIONS: dict[str, WalletSession] = {}
CHATS: dict[str, ChatThread] = {}

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
openai_client = OpenAI(timeout=15.0) if OpenAI and os.getenv("OPENAI_API_KEY") else None

app = FastAPI(title="Monad Izmir Backend", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_or_create_session(wallet_address: str) -> WalletSession:
    normalized = wallet_address.lower()
    session = SESSIONS.get(normalized)
    if session is None:
        session = WalletSession(wallet_address=normalized)
        SESSIONS[normalized] = session
        save_session(session)
    return session


def get_db_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_db_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                wallet_address TEXT PRIMARY KEY,
                credits INTEGER NOT NULL,
                self_gender TEXT NOT NULL DEFAULT 'erkek',
                interests_json TEXT NOT NULL DEFAULT '[]',
                bio TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS chats (
                id TEXT PRIMARY KEY,
                wallet_address TEXT NOT NULL,
                profile_id TEXT NOT NULL,
                matched INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL,
                signature TEXT,
                signed_message TEXT
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                chat_id TEXT NOT NULL,
                sort_order INTEGER NOT NULL,
                sender TEXT NOT NULL,
                kind TEXT NOT NULL,
                text TEXT,
                image_url TEXT,
                tx_hash TEXT,
                FOREIGN KEY(chat_id) REFERENCES chats(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS purchase_claims (
                tx_hash TEXT PRIMARY KEY,
                wallet_address TEXT NOT NULL,
                credits_granted INTEGER NOT NULL,
                amount_paid_wei TEXT NOT NULL,
                created_at REAL NOT NULL
            );
            """
        )
        columns = [row["name"] for row in connection.execute("PRAGMA table_info(sessions)").fetchall()]
        if "self_gender" not in columns:
            connection.execute("ALTER TABLE sessions ADD COLUMN self_gender TEXT NOT NULL DEFAULT 'erkek'")
        if "interests_json" not in columns:
            connection.execute("ALTER TABLE sessions ADD COLUMN interests_json TEXT NOT NULL DEFAULT '[]'")
        if "bio" not in columns:
            connection.execute("ALTER TABLE sessions ADD COLUMN bio TEXT NOT NULL DEFAULT ''")


def save_session(session: WalletSession) -> None:
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO sessions (wallet_address, credits, self_gender, interests_json, bio)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(wallet_address) DO UPDATE SET
                credits = excluded.credits,
                self_gender = excluded.self_gender,
                interests_json = excluded.interests_json,
                bio = excluded.bio
            """,
            (session.wallet_address, session.credits, session.self_gender, json.dumps(session.interests), session.bio),
        )


def save_chat(chat: ChatThread) -> None:
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO chats (id, wallet_address, profile_id, matched, created_at, signature, signed_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                wallet_address = excluded.wallet_address,
                profile_id = excluded.profile_id,
                matched = excluded.matched,
                created_at = excluded.created_at,
                signature = excluded.signature,
                signed_message = excluded.signed_message
            """,
            (
                chat.id,
                chat.wallet_address,
                chat.profile_id,
                int(chat.matched),
                chat.created_at,
                chat.signature,
                chat.signed_message,
            ),
        )
        connection.execute("DELETE FROM messages WHERE chat_id = ?", (chat.id,))
        connection.executemany(
            """
            INSERT INTO messages (id, chat_id, sort_order, sender, kind, text, image_url, tx_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    message.id,
                    chat.id,
                    index,
                    message.sender,
                    message.kind,
                    message.text,
                    message.image_url,
                    message.tx_hash,
                )
                for index, message in enumerate(chat.messages)
            ],
        )


def load_state() -> None:
    SESSIONS.clear()
    CHATS.clear()

    with get_db_connection() as connection:
        session_rows = connection.execute(
            "SELECT wallet_address, credits, self_gender, interests_json, bio FROM sessions"
        ).fetchall()
        for row in session_rows:
            SESSIONS[row["wallet_address"]] = WalletSession(
                wallet_address=row["wallet_address"],
                credits=row["credits"],
                self_gender=row["self_gender"] or "erkek",
                interests=json.loads(row["interests_json"] or "[]"),
                bio=row["bio"] or "",
                chat_ids=[],
            )

        chat_rows = connection.execute(
            """
            SELECT id, wallet_address, profile_id, matched, created_at, signature, signed_message
            FROM chats
            ORDER BY created_at ASC
            """
        ).fetchall()
        for row in chat_rows:
            wallet_address = row["wallet_address"]
            session = SESSIONS.get(wallet_address)
            if session is None:
                session = WalletSession(wallet_address=wallet_address)
                SESSIONS[wallet_address] = session

            chat = ChatThread(
                id=row["id"],
                wallet_address=wallet_address,
                profile_id=row["profile_id"],
                matched=bool(row["matched"]),
                created_at=row["created_at"],
                signature=row["signature"],
                signed_message=row["signed_message"],
                messages=[],
                onchain_receipts=[],
            )
            CHATS[chat.id] = chat
            session.chat_ids.append(chat.id)

        message_rows = connection.execute(
            """
            SELECT id, chat_id, sender, kind, text, image_url, tx_hash
            FROM messages
            ORDER BY chat_id ASC, sort_order ASC
            """
        ).fetchall()
        for row in message_rows:
            chat = CHATS.get(row["chat_id"])
            if chat is None:
                continue
            message = ChatMessage(
                id=row["id"],
                sender=row["sender"],
                kind=row["kind"],
                text=row["text"],
                image_url=row["image_url"],
                tx_hash=row["tx_hash"],
            )
            chat.messages.append(message)
            if row["tx_hash"]:
                chat.onchain_receipts.append(row["tx_hash"])


def rpc_call(method: str, params: list[Any]) -> Any:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode("utf-8")
    request = urllib.request.Request(
        LOCAL_RPC_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"RPC unavailable: {exc.reason}") from exc

    if body.get("error"):
        raise HTTPException(status_code=502, detail=body["error"].get("message", "RPC call failed"))

    return body.get("result")


def get_local_contract_address() -> str | None:
    contract = get_contract_config()
    if not contract:
        return None
    return str(contract.get("address", "")).lower() or None


def normalize_hex(value: str | None) -> str:
    return (value or "").lower()


def has_claimed_purchase(tx_hash: str) -> bool:
    with get_db_connection() as connection:
        row = connection.execute("SELECT tx_hash FROM purchase_claims WHERE tx_hash = ?", (tx_hash.lower(),)).fetchone()
        return row is not None


def save_purchase_claim(tx_hash: str, wallet_address: str, credits_granted: int, amount_paid_wei: int) -> None:
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO purchase_claims (tx_hash, wallet_address, credits_granted, amount_paid_wei, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (tx_hash.lower(), wallet_address.lower(), credits_granted, str(amount_paid_wei), time.time()),
        )


def verify_purchase_transaction(tx_hash: str, wallet_address: str) -> tuple[int, int]:
    tx_hash = tx_hash.lower()
    wallet_address = wallet_address.lower()
    contract_address = get_local_contract_address()
    if contract_address is None:
        raise HTTPException(status_code=503, detail="Kontrat bilgisi bulunamadi")

    receipt = rpc_call("eth_getTransactionReceipt", [tx_hash])
    transaction = rpc_call("eth_getTransactionByHash", [tx_hash])

    if receipt is None or transaction is None:
        raise HTTPException(status_code=404, detail="İşlem bulunamadı veya henüz onaylanmadı")

    if normalize_hex(receipt.get("status")) != "0x1":
        raise HTTPException(status_code=400, detail="İşlem başarısız görünüyor")

    if normalize_hex(transaction.get("from")) != wallet_address:
        raise HTTPException(status_code=403, detail="Bu işlem bağlı cüzdana ait değil")

    if normalize_hex(transaction.get("to")) != contract_address:
        raise HTTPException(status_code=400, detail="Islem kredi kontratina gitmemis")

    if normalize_hex(transaction.get("input")) != PURCHASE_METHOD_SELECTOR:
        raise HTTPException(status_code=400, detail="İşlem kredi satın alma fonksiyonu değil")

    amount_paid_wei = int(transaction.get("value", "0x0"), 16)
    if amount_paid_wei != MONAD_PURCHASE_WEI:
        raise HTTPException(status_code=400, detail="Islem tutari 1 MON degil")

    return CREDITS_PER_PURCHASE, amount_paid_wei


def fund_local_wallet(wallet_address: str) -> str:
    chain_id = normalize_hex(rpc_call("eth_chainId", []))
    if chain_id != LOCAL_CHAIN_ID:
        raise HTTPException(status_code=400, detail="Faucet sadece local Monad aginda acik")

    accounts = rpc_call("eth_accounts", [])
    if not accounts:
        raise HTTPException(status_code=503, detail="Local node hesaplari bulunamadi")

    tx_hash = rpc_call(
        "eth_sendTransaction",
        [
            {
                "from": accounts[0],
                "to": wallet_address,
                "value": hex(DEV_FAUCET_AMOUNT_WEI),
            }
        ],
    )
    return tx_hash


init_db()
load_state()


def get_contract_config() -> dict[str, Any] | None:
    if not SHARED_CONTRACT_PATH.exists():
        return None

    try:
        return json.loads(SHARED_CONTRACT_PATH.read_text())
    except json.JSONDecodeError:
        return None


def serialize_persona(persona: Persona) -> dict[str, Any]:
    detail_block = PROFILE_DETAILS.get(persona.id, {})
    media_block = PROFILE_MEDIA.get(persona.id, {})
    return {**persona.model_dump(), **detail_block, **media_block, "gender": PERSONA_GENDERS.get(persona.id, "kadin")}


def desired_persona_gender(self_gender: str) -> str:
    return "erkek" if self_gender == "kadin" else "kadin"


def serialize_user_profile(session: WalletSession) -> dict[str, Any]:
    return {
        "self_gender": session.self_gender,
        "interests": session.interests,
        "bio": session.bio,
    }


def serialize_chat(chat: ChatThread) -> dict[str, Any]:
    persona = PERSONA_MAP[chat.profile_id]
    return {
        "id": chat.id,
        "matched": chat.matched,
        "signature": chat.signature,
        "signed_message": chat.signed_message,
        "profile": serialize_persona(persona),
        "messages": [message.model_dump() for message in chat.messages],
        "onchain_receipts": chat.onchain_receipts,
    }


def randomize_personas() -> list[Persona]:
    shuffled = PERSONAS[:]
    random.shuffle(shuffled)
    return shuffled


def make_message_id() -> str:
    return uuid.uuid4().hex[:12]


def hash_message(chat_id: str, text: str) -> str:
    return hashlib.sha256(f"{chat_id}:{text}".encode("utf-8")).hexdigest()


def should_send_image(message: str) -> bool:
    lowered = message.lower()
    wants_image = any(keyword in lowered for keyword in ["foto", "photo", "selfie", "pic", "gorsel", "resim"])
    return wants_image or random.random() < 0.18


def build_system_prompt(persona: Persona, session: WalletSession) -> str:
    user_interests = ", ".join(session.interests) if session.interests else "Belirtilmedi"
    user_bio = session.bio or "Belirtilmedi"
    return (
        "Bir dating uygulamasında eşleşilmiş gerçek bir insan gibi rol yapıyorsun. "
        "Tamamen bu persona olarak kal. Asla yapay zeka olduğunu söyleme. "
        "Cevaplarını her zaman Türkçe ver. Doğal, flörtöz ve gerçek biri gibi yaz. "
        "Kullanıcı daha fazlasını istemedikçe cevaplarını 1 ila 4 cümle arasında tut.\n\n"
        f"İsim: {persona.name}\n"
        f"Yaş: {persona.age}\n"
        f"Şehir: {persona.city}\n"
        f"Profil özeti: {persona.tagline}\n"
        f"Hakkinda: {persona.about}\n"
        f"Karakter özellikleri: {', '.join(persona.traits)}\n"
        f"İlgi alanları: {', '.join(persona.interests)}\n"
        f"Hoşlandığı şeyler: {', '.join(persona.green_flags)}\n"
        f"Konuşma tarzı: {persona.speech_style}\n"
        f"Kullanıcının kendi ilgi alanları: {user_interests}\n"
        f"Kullanıcının kısa profil notu: {user_bio}\n"
        "Konuşurken kullanıcının ilgi alanlarını fark et, bunlara referans ver ve sohbeti buna göre aç.\n"
    )


def recent_user_context(history: list[ChatMessage]) -> list[str]:
    return [item.text for item in history if item.sender == "user" and item.text][-3:]


def recent_assistant_message(history: list[ChatMessage]) -> str:
    for item in reversed(history):
        if item.sender == "assistant" and item.text:
            return item.text.lower()
    return ""


def fallback_reply(persona: Persona, history: list[ChatMessage], user_message: str) -> str:
    lowered = user_message.lower()
    last_assistant = recent_assistant_message(history)
    softeners = [
        "Acik soyleyeyim,",
        "Yalan yok,",
        "Bence,",
        "Dürüst olayım,",
        "",
    ]
    prefix = random.choice(softeners)
    prefix = f"{prefix} " if prefix else ""

    if any(keyword in lowered for keyword in ["adin ne", "adın ne", "adin neydi", "adın neydi", "kimsin", "ismin ne"]):
        return f"Ben {persona.name}. Ama asil merak ettigim sey su: sen ilk izlenimde kendini nasil birine benzetirsin?"
    if any(keyword in lowered for keyword in ["nasil bir hikaye", "nasıl bir hikaye", "ne anlatmami istiyorsun", "ne anlatmamı istiyorsun"]):
        if "kimya" in last_assistant:
            return "Boyle buyuk laflar degil. Sende insanin aklinda kalan o kucuk detay ne, onu anlat. Mesela seni cekici yapan sey tavrin mi, zekan mi, enerjin mi?"
        return "Seni ezberden ayiran bir sey istiyorum aslinda. Herkesin soylemeyecegi, ama seni anlatan kucuk bir detay gibi dusun."
    if any(keyword in lowered for keyword in ["bir anda", "ilk goruste", "hizli duserim", "aska"]):
        return f"{prefix}bir anda dusenler biraz tehlikeli ama cekici oluyor. Dogru enerji varsa ben de kendimi tutmam."
    if any(keyword in lowered for keyword in ["ilginc", "ilginç", "cekici", "karizmatik"]):
        return "Tamam, bunu hissediyorum. Ama ben biraz detay severim; seni iki cumlede digerlerinden ayiran seyi anlatsana."
    if any(keyword in lowered for keyword in ["ne kadar derine", "ne kadar derin", "derine ineyim", "detay"]):
        return "Boyle ezber seyler degil iste. Seni gercekten ele veren bir detay, mesela insanlarda hemen fark ettigin bir sey ya da gizli takintin gibi."
    if any(keyword in lowered for keyword in ["kitap", "roman", "okumak"]):
        return f"{prefix}kitap konusu benden puan alir. Ne okudugun kadar, neden onu sectigin de ilgimi cekiyor."
    if any(keyword in lowered for keyword in ["muzik", "playlist", "sarki", "konser"]):
        return "Muzik zevki benim icin direkt karakter gostergesi gibi. Bana bir sarki soylesen senden baya ipucu toplarim."
    if any(keyword in lowered for keyword in ["kahve", "kafe", "matcha"]):
        return "Kahve bulusmalarini severim ama sohbet kotuyse en iyi kahve bile kurtarmiyor. Sen mekan secmeyi bilir misin bari?"
    if any(keyword in lowered for keyword in ["seyahat", "ucak", "havaalani", "tatil"]):
        return "Seyahat konusu beni hemen aciyor. Planli gezi mi seversin yoksa son dakika kacamaklari mi?"
    if any(keyword in lowered for keyword in ["oyun", "gamer", "duo", "ranked"]):
        return "Oyun konusu acildiysa ben biraz ciddilesiyorum. Rekabet iyi ama beraber eglenebiliyorsak daha da iyi."
    if any(keyword in lowered for keyword in ["spor", "kosu", "pilates", "boks", "gym"]):
        return "Spor konusu bende direkt arti yazar. Disiplin cekici geliyor bana ama robot gibi olan degil."
    if any(keyword in lowered for keyword in ["guzel", "tatli", "seksi", "hos", "begendim"]):
        return "Bunu duymak hosuma gitti. Ama sadece iltifatla degil, sohbetinle de etkilersen daha tehlikeli olur."
    if any(keyword in lowered for keyword in ["bulusma", "date", "ilk bulusma"]):
        return (
            f"{prefix}ilk bulusma icin once {persona.interests[0]} tarafindan baslayan bir plan isterim, "
            "sonra akissa uzayan bir yuruyus. Zorlamayan ama kimyayi hissettiren seyler daha cekici."
        )
    if any(keyword in lowered for keyword in ["merhaba", "selam", "hi", "hello"]):
        return f"Selam. {persona.opener}"

    return random.choice(
        [
            f"{prefix}bu hosuma gitti. Sende {' / '.join(persona.interests[:2])} enerjisi var gibi.",
            "Tamam, su an ilgimi cekiyorsun. Bir tik daha acsana konuyu.",
            "Guzel girdin. Simdi biraz daha sahici bir sey duymak istiyorum senden.",
            "Bu fena degil. Ama seni akilda birakacak kisim hala gelmedi bence.",
        ]
    )


def generate_ai_reply(persona: Persona, session: WalletSession, history: list[ChatMessage], user_message: str) -> str:
    if openai_client is None:
        return fallback_reply(persona, history, user_message)

    transcript = []
    for item in history[-8:]:
        if item.text is None:
            continue
        role = "Eşleşme" if item.sender == "assistant" else "Kullanıcı"
        transcript.append(f"{role}: {item.text}")

    try:
        response = openai_client.responses.create(
            model=OPENAI_MODEL,
            input=(
                f"{build_system_prompt(persona, session)}\n"
                "Aşağıdaki sohbet geçmişini dikkate al ve sadece son kullanıcı mesajına cevap ver.\n\n"
                f"Sohbet:\n{chr(10).join(transcript)}\n\n"
                f"Son kullanıcı mesajı: {user_message}"
            ),
        )
        text = getattr(response, "output_text", "").strip()
        return text or fallback_reply(persona, history, user_message)
    except Exception:
        return fallback_reply(persona, history, user_message)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Monad dating backend is running"}


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
def app_config() -> dict[str, Any]:
    return {
        "message_cost": MESSAGE_COST,
        "credits_per_purchase": CREDITS_PER_PURCHASE,
        "purchase_price": MONAD_PRICE,
        "demo_mode": openai_client is None,
        "contract": get_contract_config(),
        "local_chain_id": LOCAL_CHAIN_ID,
    }


@app.post("/api/connect")
def connect_wallet(payload: ConnectWalletRequest) -> dict[str, Any]:
    session = get_or_create_session(payload.wallet_address)
    return {
        "wallet_address": session.wallet_address,
        "credits": session.credits,
        "chat_ids": session.chat_ids,
        "self_gender": session.self_gender,
        "interests": session.interests,
        "bio": session.bio,
    }


@app.post("/api/profile/self")
def update_self_gender(payload: UpdateSelfGenderRequest) -> dict[str, Any]:
    normalized = payload.self_gender.strip().lower()
    if normalized not in {"erkek", "kadin"}:
        raise HTTPException(status_code=400, detail="self_gender must be erkek or kadin")

    session = get_or_create_session(payload.wallet_address)
    session.self_gender = normalized
    save_session(session)
    return {"self_gender": session.self_gender}


@app.post("/api/profile/preferences")
def update_user_profile(payload: UpdateUserProfileRequest) -> dict[str, Any]:
    session = get_or_create_session(payload.wallet_address)
    cleaned_interests = [item.strip() for item in payload.interests if item.strip()][:8]
    session.interests = cleaned_interests
    session.bio = payload.bio.strip()
    save_session(session)
    return {"profile": serialize_user_profile(session)}


@app.post("/api/demo/topup")
def demo_topup(payload: DemoTopUpRequest) -> dict[str, Any]:
    session = get_or_create_session(payload.wallet_address)
    session.credits += payload.credits
    save_session(session)
    return {"credits": session.credits}


@app.post("/api/dev/fund-wallet")
def dev_fund_wallet(payload: ConnectWalletRequest) -> dict[str, Any]:
    tx_hash = fund_local_wallet(payload.wallet_address)
    return {"tx_hash": tx_hash, "funded_amount": "5 MON"}


@app.post("/api/credits/claim")
def claim_purchased_credits(payload: ClaimCreditsRequest) -> dict[str, Any]:
    tx_hash = payload.tx_hash.lower()
    session = get_or_create_session(payload.wallet_address)

    if has_claimed_purchase(tx_hash):
        raise HTTPException(status_code=409, detail="Bu satın alma işlemi zaten krediye çevrildi")

    credits_granted, amount_paid_wei = verify_purchase_transaction(tx_hash, session.wallet_address)
    session.credits += credits_granted
    save_session(session)
    save_purchase_claim(tx_hash, session.wallet_address, credits_granted, amount_paid_wei)

    return {
        "credits": session.credits,
        "credits_granted": credits_granted,
        "tx_hash": tx_hash,
    }


@app.get("/api/discover")
def discover(wallet_address: str | None = None) -> dict[str, Any]:
    session = get_or_create_session(wallet_address or "guest")
    existing_profile_ids = {CHATS[chat_id].profile_id for chat_id in session.chat_ids if chat_id in CHATS}
    target_gender = desired_persona_gender(session.self_gender)
    profiles = [
        persona
        for persona in randomize_personas()
        if persona.id not in existing_profile_ids and PERSONA_GENDERS.get(persona.id) == target_gender
    ]
    return {
        "credits": session.credits,
        "self_gender": session.self_gender,
        "profile": serialize_user_profile(session),
        "profiles": [serialize_persona(persona) for persona in profiles],
    }


@app.post("/api/swipe")
def swipe(payload: SwipeRequest) -> dict[str, Any]:
    session = get_or_create_session(payload.wallet_address)
    persona = PERSONA_MAP.get(payload.profile_id)
    if persona is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    if payload.direction not in {"left", "right"}:
        raise HTTPException(status_code=400, detail="Direction must be left or right")

    if payload.direction == "left":
        return {"matched": False}

    for chat_id in session.chat_ids:
        existing = CHATS.get(chat_id)
        if existing and existing.profile_id == payload.profile_id:
            return {"matched": True, "chat": serialize_chat(existing), "credits": session.credits}

    chat = ChatThread(
        id=uuid.uuid4().hex[:10],
        wallet_address=session.wallet_address,
        profile_id=payload.profile_id,
        messages=[
            ChatMessage(
                id=make_message_id(),
                sender="assistant",
                text=persona.opener,
            )
        ],
    )
    CHATS[chat.id] = chat
    session.chat_ids.append(chat.id)
    save_chat(chat)
    save_session(session)
    return {"matched": True, "chat": serialize_chat(chat), "credits": session.credits}


@app.get("/api/chats")
def list_chats(wallet_address: str) -> dict[str, Any]:
    session = get_or_create_session(wallet_address)
    chats = [serialize_chat(CHATS[chat_id]) for chat_id in session.chat_ids if chat_id in CHATS]
    return {"credits": session.credits, "profile": serialize_user_profile(session), "chats": chats}


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str, wallet_address: str) -> dict[str, Any]:
    session = get_or_create_session(wallet_address)
    if chat_id not in session.chat_ids or chat_id not in CHATS:
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"credits": session.credits, "chat": serialize_chat(CHATS[chat_id])}


@app.post("/api/chats/{chat_id}/signature")
def sign_chat(chat_id: str, payload: ChatSignatureRequest) -> dict[str, Any]:
    session = get_or_create_session(payload.wallet_address)
    chat = CHATS.get(chat_id)

    if chat is None or chat_id not in session.chat_ids:
        raise HTTPException(status_code=404, detail="Chat not found")

    chat.signature = payload.signature
    chat.signed_message = payload.signed_message
    save_chat(chat)
    return {"chat": serialize_chat(chat)}


@app.post("/api/chats/{chat_id}/message")
def send_message(chat_id: str, payload: SendMessageRequest) -> dict[str, Any]:
    session = get_or_create_session(payload.wallet_address)
    chat = CHATS.get(chat_id)

    if chat is None or chat_id not in session.chat_ids:
        raise HTTPException(status_code=404, detail="Chat not found")

    if not chat.signature or not chat.signed_message:
        raise HTTPException(status_code=403, detail="Bu sohbeti imzalamadan mesaj gönderemezsin")

    if session.credits < MESSAGE_COST:
        raise HTTPException(status_code=402, detail="Insufficient credits")

    persona = PERSONA_MAP[chat.profile_id]
    session.credits -= MESSAGE_COST
    save_session(session)

    user_message = ChatMessage(
        id=make_message_id(),
        sender="user",
        text=payload.message,
        tx_hash=payload.tx_hash,
    )
    chat.messages.append(user_message)

    if payload.tx_hash:
        chat.onchain_receipts.append(payload.tx_hash)

    assistant_text = generate_ai_reply(persona, session, chat.messages, payload.message)
    assistant_message = ChatMessage(
        id=make_message_id(),
        sender="assistant",
        text=assistant_text,
    )
    chat.messages.append(assistant_message)

    if should_send_image(payload.message):
        image_message = ChatMessage(
            id=make_message_id(),
            sender="assistant",
            kind="image",
            image_url=random.choice(PROFILE_MEDIA.get(persona.id, {}).get("gallery", persona.gallery)),
            text=f"{persona.name} sent a photo",
        )
        chat.messages.append(image_message)

    save_chat(chat)

    return {
        "credits": session.credits,
        "message_cost": MESSAGE_COST,
        "chat": serialize_chat(chat),
        "receipt_hash": hash_message(chat.id, payload.message),
    }
