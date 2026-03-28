# Monad Match

Monad Match, Tinder benzeri swipe deneyimini yapay zekâ destekli sohbet, MetaMask cüzdan bağlantısı ve Monad uyumlu kontrat yapısıyla birleştiren deneysel bir dating app MVP'sidir.

Kullanıcı:
- MetaMask ile bağlanır
- Profilinde kendini `Erkek` veya `Kadın` olarak seçer
- Kendi ilgi alanlarını ve kısa profil notunu ekler
- Keşfet ekranında profilleri sağa veya sola kaydırır
- Eşleşme oluşunca sohbeti bir kez imzalar
- Sonrasında AI persona ile doğal sohbet eder

AI persona tarafı, kullanıcının ilgi alanlarını ve profil notunu görerek buna göre daha kişisel konuşmalar açar.

## Özellikler

- FastAPI backend
- React + Vite frontend
- Hardhat + Solidity kontrat katmanı
- Docker tabanlı çok servisli geliştirme ortamı
- Ayrı sayfalı frontend yapısı:
  - `Profil`
  - `Keşfet`
  - `Mesajlar`
  - `Cüzdan`
- Kalıcı veri saklama:
  - sohbet geçmişi
  - kredi bakiyesi
  - cinsiyet tercihi
  - kullanıcı ilgi alanları
  - profil notu
- Tek seferlik sohbet imzası
- Görsel büyütme modalı
- Türkçe arayüz
- Hot reload destekli frontend ve backend geliştirme akışı

## Mimari

### Frontend

- React + Vite
- Ana dosya: [frontend/src/App.jsx](/home/gotunc/monad-izmir/frontend/src/App.jsx)
- Stil dosyası: [frontend/src/styles.css](/home/gotunc/monad-izmir/frontend/src/styles.css)

### Backend

- FastAPI
- Ana dosya: [backend/app/main.py](/home/gotunc/monad-izmir/backend/app/main.py)
- Kalıcı veri: [backend/data/monad_match.db](/home/gotunc/monad-izmir/backend/data/monad_match.db)

### Contracts

- Hardhat
- Kontrat: [contracts/contracts/MonadMatchCredits.sol](/home/gotunc/monad-izmir/contracts/contracts/MonadMatchCredits.sol)
- Hardhat config: [contracts/hardhat.config.js](/home/gotunc/monad-izmir/contracts/hardhat.config.js)
- Deploy script: [contracts/scripts/deploy.js](/home/gotunc/monad-izmir/contracts/scripts/deploy.js)

## Çalışma Mantığı

### Profil ve keşfet

- Kullanıcı `Erkek` seçerse keşfette kadın profiller gösterilir
- Kullanıcı `Kadın` seçerse keşfette kaslı erkek profiller gösterilir
- Kullanıcı ilgi alanlarını ve kısa notunu profil ekranından kaydedebilir

### Sohbet

- Sağa kaydırınca eşleşme oluşur
- Sohbet ilk açıldığında MetaMask ile bir kez imzalanır
- Sonraki mesajlarda tekrar imza istenmez
- Mesajlar kalıcı olarak saklanır

### AI davranışı

- AI persona, eşleşilen profil gibi davranır
- Türkçe konuşur
- Sohbet geçmişini dikkate alır
- Kullanıcının ilgi alanlarını ve profil notunu kullanarak daha kişisel konuşur
- Gerekirse görsel mesaj da gönderebilir

## Servisler

Bu proje üç ana servisten oluşur:

- `backend`
- `frontend`
- `contracts`

Canlı erişim portları bu makinede şu şekilde kullanılıyor:

- Frontend: `http://isinigetir.com:3001`
- Backend: `http://isinigetir.com:8001`
- Backend health: `http://isinigetir.com:8001/health`
- Hardhat RPC: `http://127.0.0.1:8546`

## Kurulum

### 1. Ortam dosyasını hazırla

Repo kökünde `.env` dosyası bulunmalı. Örnek değişkenler:

```env
BACKEND_PORT=8001
FRONTEND_PORT=3001
CONTRACTS_PORT=8546
MONAD_RPC_URL=https://testnet-rpc.monad.xyz
PRIVATE_KEY=replace_with_test_wallet_private_key
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-5
```

### 2. Docker ile ayağa kaldır

```bash
docker-compose up --build
```

Not:
- Bu ortamda `docker-compose` v1 kullanılıyor
- Bazen `ContainerConfig` recreate bug'ı çıkabiliyor
- Böyle bir durumda container'ları silip yeniden ayağa kaldırmak gerekebilir

### 3. Frontend ve backend hot reload

Projede hot reload açıktır:

- frontend dosya değişiklikleri canlı yenilenir
- backend dosya değişiklikleri `uvicorn --reload` ile yeniden yüklenir

## Geliştirme Notları

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Build almak için:

```bash
cd frontend
npm run build
```

### Backend

```bash
python3 -m py_compile backend/app/main.py
```

### Contracts

```bash
cd contracts
npx hardhat compile
npx hardhat test
```

Kontrat deploy etmek için:

```bash
cd contracts
npx hardhat run scripts/deploy.js --network localhost
```

## API Özeti

Başlıca endpoint'ler:

- `POST /api/connect`
- `GET /api/config`
- `GET /api/discover`
- `POST /api/swipe`
- `GET /api/chats`
- `POST /api/chats/{chat_id}/signature`
- `POST /api/chats/{chat_id}/message`
- `POST /api/profile/self`
- `POST /api/profile/preferences`
- `POST /api/credits/claim`
- `POST /api/dev/fund-wallet`

## Kalıcılık

Backend artık RAM yerine SQLite kullanır. Şu bilgiler kalıcıdır:

- kredi bakiyesi
- kullanıcı cinsiyet tercihi
- kullanıcı ilgi alanları
- kullanıcı bio/notu
- chat listesi
- sohbet mesajları
- sohbet imzası

Yani kullanıcı tekrar giriş yaptığında eski sohbetlerini ve profil ayarlarını geri görür.

## Güvenlik ve Notlar

- Bu proje MVP / demo niteliğindedir
- OpenAI anahtarı `.env` içinde tutuluyorsa production için ayrı secret yönetimi önerilir
- Local Hardhat ağı geliştirme amaçlıdır
- Gerçek Monad testnet/mainnet kullanımı için kontrat deploy ve RPC ayarları ayrıca yapılandırılmalıdır

## Yol Haritası

İleride eklenebilecek geliştirmeler:

- gerçek kullanıcı auth sistemi
- daha zengin profil editörü
- gelişmiş filtreleme
- medya yükleme
- gerçek testnet deploy akışı
- admin paneli
- moderasyon ve güvenlik katmanı
