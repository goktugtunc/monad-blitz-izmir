import { useEffect, useRef, useState } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { ethers } from "ethers";

const backendPort = import.meta.env.VITE_BACKEND_PORT || "8001";
const contractsPort = import.meta.env.VITE_CONTRACTS_PORT || "8546";

const baseUrl =
  typeof window === "undefined"
    ? `http://localhost:${backendPort}`
    : `${window.location.protocol}//${window.location.hostname}:${backendPort}`;

const rpcUrl =
  typeof window === "undefined"
    ? `http://127.0.0.1:${contractsPort}`
    : `http://127.0.0.1:${contractsPort}`;

const initialDrag = { active: false, startX: 0, deltaX: 0 };

function shortAddress(value) {
  if (!value) {
    return "Wallet bagli degil";
  }

  return `${value.slice(0, 6)}...${value.slice(-4)}`;
}

async function fetchJson(path, options) {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }
  return data;
}

async function upsertLocalChain() {
  await window.ethereum.request({
    method: "wallet_addEthereumChain",
    params: [
      {
        chainId: "0x7a6a",
        chainName: "Monad Match Local",
        nativeCurrency: { name: "MON", symbol: "MON", decimals: 18 },
        rpcUrls: [rpcUrl]
      }
    ]
  });
}

function hashText(text) {
  return ethers.id(text);
}

function getChatIdBytes(chatId) {
  return ethers.keccak256(ethers.toUtf8Bytes(chatId));
}

function getProfileIdBytes(profileId) {
  return ethers.keccak256(ethers.toUtf8Bytes(profileId));
}

function buildChatSignatureMessage(chat, walletAddress) {
  return [
    "Monad Match Sohbet İmzası",
    `Sohbet ID: ${chat.id}`,
    `Profil: ${chat.profile.name}`,
    `Profil ID: ${chat.profile.id}`,
    `Cüzdan: ${walletAddress}`,
    "Bu sohbeti başlattığımı ve bu eşleşmeyi onayladığımı imzalıyorum."
  ].join("\n");
}

function SwipeCard({ profile, drag, onPointerDown, onSwipe, onOpenImage }) {
  const rotation = drag.deltaX / 18;
  const opacity = Math.max(0.35, 1 - Math.abs(drag.deltaX) / 260);

  return (
    <article
      className="swipe-card"
      style={{
        transform: `translateX(${drag.deltaX}px) rotate(${rotation}deg)`,
        opacity
      }}
      onPointerDown={onPointerDown}
    >
      <div className="swipe-media">
        <img
          src={profile.photo_url}
          alt={profile.name}
          className="zoomable-image"
          onClick={() => onOpenImage(profile.photo_url, profile.name)}
        />
        <div className="swipe-overlay">
          <div>
            <p className="swipe-city">{profile.city}</p>
            <h2>
              {profile.name}, {profile.age}
            </h2>
            <p className="swipe-tagline">{profile.tagline}</p>
          </div>
          <div className="chip-row">
            {profile.traits.map((trait) => (
              <span className="chip" key={trait}>
                {trait}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="swipe-body">
        <p>{profile.about}</p>
        <div className="detail-grid">
          <div className="stat-block">
            <span>Meslek</span>
            <strong>{profile.profession}</strong>
          </div>
          <div className="stat-block">
            <span>Egitim</span>
            <strong>{profile.education}</strong>
          </div>
        </div>
        <div className="stat-block">
          <span>İlgi alanları</span>
          <strong>{profile.interests.join(" • ")}</strong>
        </div>
        <div className="stat-block">
          <span>Hoşlandığı şeyler</span>
          <strong>{profile.green_flags.join(" • ")}</strong>
        </div>
        <div className="stat-block">
          <span>Ne arıyor</span>
          <strong>{profile.looking_for}</strong>
        </div>
        <div className="stat-block">
          <span>İdeal buluşma</span>
          <strong>{profile.ideal_date}</strong>
        </div>
        <div className="stat-block">
          <span>Hafta sonu modu</span>
          <strong>{profile.weekend_plan}</strong>
        </div>
        <div className="stat-block">
          <span>Takıldığı yerler</span>
          <strong>{profile.neighborhoods.join(" • ")}</strong>
        </div>
        <div className="stat-block">
          <span>Deal breaker</span>
          <strong>{profile.deal_breakers.join(" • ")}</strong>
        </div>

        <div className="gallery-strip">
          {profile.gallery.slice(0, 3).map((image) => (
            <img
              key={image}
              src={image}
              alt={`${profile.name} gallery`}
              className="zoomable-image"
              onClick={() => onOpenImage(image, profile.name)}
            />
          ))}
        </div>

        <div className="action-row">
          <button className="ghost-button" onClick={() => onSwipe("left")}>
            Sola geç
          </button>
          <button className="primary-button" onClick={() => onSwipe("right")}>
            Sağa kaydır ve eşleş
          </button>
        </div>
      </div>
    </article>
  );
}

function WalletPage({
  walletAddress,
  credits,
  config,
  status,
  onConnect
}) {
  return (
    <section className="page-card">
      <div className="page-heading">
        <p className="eyebrow">Cüzdan</p>
        <h2>MetaMask bağla ve kredi ekonomisini yönet.</h2>
      </div>

      <div className="wallet-card wallet-page-card">
        <div className="wallet-row">
          <div>
            <span className="label">Bagli cüzdan</span>
            <strong>{shortAddress(walletAddress)}</strong>
          </div>
          <button className="ghost-button" onClick={onConnect}>
            {walletAddress ? "Yeniden bağla" : "MetaMask bağla"}
          </button>
        </div>

        <div className="wallet-grid">
          <div className="metric-card">
            <span>Kredi</span>
            <strong>{credits}</strong>
          </div>
          <div className="metric-card">
            <span>Mesaj maliyeti</span>
            <strong>{config?.message_cost || 25}</strong>
          </div>
          <div className="metric-card">
            <span>Paket</span>
            <strong>
              {config?.credits_per_purchase || 1000} / {config?.purchase_price || "1 MON"}
            </strong>
          </div>
        </div>

        <p className="tiny-text">
          {config?.demo_mode
            ? "OpenAI anahtarı yoksa backend demo karakter cevabı kullanır."
            : "OpenAI bağlantısı aktif."}
        </p>
        <p className="tiny-text">Durum: {status}</p>
      </div>
    </section>
  );
}

function ProfilePage({
  walletAddress,
  credits,
  chats,
  config,
  status,
  selfGender,
  userInterestsInput,
  setUserInterestsInput,
  userBioInput,
  setUserBioInput,
  onChangeSelfGender,
  onSaveProfile
}) {
  const activeMatches = chats.length;

  return (
    <section className="page-card">
      <div className="page-heading">
        <p className="eyebrow">Profil</p>
        <h2>Hesap özeti ve dating ritmin tek bakışta.</h2>
      </div>

      <div className="profile-grid">
        <article className="hero-profile-card">
          <span className="label">Kimlik</span>
          <h3>{shortAddress(walletAddress)}</h3>
          <p>
            Monad Match hesabın kredi bazlı mesajlaşma mantığıyla çalışıyor. Her mesaj {config?.message_cost || 25}
            kredi harcar.
          </p>
          <div className="gender-selector">
            <span className="label">Ben</span>
            <div className="toggle-row">
              <button
                className={selfGender === "erkek" ? "toggle-chip active" : "toggle-chip"}
                onClick={() => onChangeSelfGender("erkek")}
                type="button"
              >
                Erkek
              </button>
              <button
                className={selfGender === "kadin" ? "toggle-chip active" : "toggle-chip"}
                onClick={() => onChangeSelfGender("kadin")}
                type="button"
              >
                Kadın
              </button>
            </div>
            <p className="tiny-text">
              Erkek seçersen kadınlar, kadın seçersen kaslı erkekler gösterilir.
            </p>
          </div>
          <div className="profile-editor">
            <label className="profile-field">
              <span className="label">İlgi alanlarım</span>
              <input
                value={userInterestsInput}
                onChange={(event) => setUserInterestsInput(event.target.value)}
                placeholder="Örnek: spor, kahve, sinema, seyahat"
              />
            </label>
            <label className="profile-field">
              <span className="label">Kısa profil notum</span>
              <textarea
                value={userBioInput}
                onChange={(event) => setUserBioInput(event.target.value)}
                placeholder="Kendini kısaca anlat. AI eşleşmeler bunu görüp konuşmayı buna göre açsın."
              />
            </label>
            <button className="primary-button" type="button" onClick={onSaveProfile}>
              Profilimi kaydet
            </button>
          </div>
        </article>

        <article className="metric-card profile-metric">
          <span>Aktif kredi</span>
          <strong>{credits}</strong>
        </article>

        <article className="metric-card profile-metric">
          <span>Aktif eşleşme</span>
          <strong>{activeMatches}</strong>
        </article>

        <article className="metric-card profile-metric">
          <span>Kredi paketi</span>
          <strong>{config?.credits_per_purchase || 1000}</strong>
        </article>

        <article className="status-card">
          <span className="label">Son durum</span>
          <p>{status}</p>
        </article>
      </div>
    </section>
  );
}

function DiscoverPage({
  walletAddress,
  profiles,
  drag,
  onPointerDown,
  onSwipe,
  onRefresh,
  onGoWallet,
  onOpenImage
}) {
  const topProfile = profiles[0] || null;

  return (
    <section className="page-card">
      <div className="page-heading">
        <p className="eyebrow">Keşfet</p>
        <h2>Profilleri sağa ve sola kaydırarak yeni sohbetler aç.</h2>
      </div>

      <div className="discover-layout">
        {!walletAddress ? (
          <div className="empty-card">
            <h2>Önce cüzdan bağla</h2>
            <p>Sağa veya sola kaydırabilmek ve eşleşme açabilmek için önce MetaMask bağlaman gerekiyor.</p>
            <button className="primary-button" onClick={onGoWallet}>
              Cüzdan sayfasına git
            </button>
          </div>
        ) : topProfile ? (
          <SwipeCard
            profile={topProfile}
            drag={drag}
            onPointerDown={onPointerDown}
            onSwipe={onSwipe}
            onOpenImage={onOpenImage}
          />
        ) : (
          <div className="empty-card">
            <h2>Yeni profil kalmadı</h2>
            <p>Keşfet listesini yenilemek için butona bas.</p>
            <button className="primary-button" onClick={() => onRefresh(walletAddress)}>
              Profilleri yenile
            </button>
          </div>
        )}

        <div className="stack-preview">
          {profiles.slice(1, 4).map((profile) => (
            <div className="mini-card" key={profile.id}>
              <img
                src={profile.photo_url}
                alt={profile.name}
                className="zoomable-image"
                onClick={() => onOpenImage(profile.photo_url, profile.name)}
              />
              <div>
                <strong>{profile.name}, {profile.age}</strong>
                <span>{profile.city} • {profile.profession}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function MessagesPage({
  chats,
  activeChatId,
  setActiveChatId,
  activeChat,
  config,
  messageInput,
  setMessageInput,
  isSending,
  onSend,
  onRequireSignature,
  onOpenImage,
  userProfile
}) {
  const isChatSigned = Boolean(activeChat?.signature);

  return (
    <section className="page-card page-fill">
      <div className="page-heading page-heading-compact">
        <p className="eyebrow">Mesajlar</p>
        <h2>Eşleşmelerinle zincire kayıtlı sohbetler.</h2>
      </div>

      <div className="messages-layout route-messages-layout">
        <aside className="chat-list">
          {chats.length === 0 ? <div className="empty-chat">Sağa kaydırdığın kişiler burada görünecek.</div> : null}

          {chats.map((chat) => (
            <button
              key={chat.id}
              className={chat.id === activeChatId ? "chat-pill active" : "chat-pill"}
              onClick={() => setActiveChatId(chat.id)}
            >
              <img
                src={chat.profile.photo_url}
                alt={chat.profile.name}
                className="zoomable-image"
                onClick={(event) => {
                  event.stopPropagation();
                  onOpenImage(chat.profile.photo_url, chat.profile.name);
                }}
              />
              <div>
                <strong>{chat.profile.name}</strong>
                <span>{chat.profile.tagline}</span>
              </div>
            </button>
          ))}
        </aside>

        <section className="chat-panel">
          {activeChat ? (
            <>
              <header className="chat-header">
                <div className="chat-user">
                  <img
                    src={activeChat.profile.photo_url}
                    alt={activeChat.profile.name}
                    className="zoomable-image"
                    onClick={() => onOpenImage(activeChat.profile.photo_url, activeChat.profile.name)}
                  />
                  <div>
                    <strong>{activeChat.profile.name}</strong>
                    <span>{activeChat.profile.city}</span>
                  </div>
                </div>
                <div className="chat-meta">
                  <span>{config?.message_cost || 25} kredi / mesaj</span>
                  <span>{activeChat.signature ? "imzalı sohbet" : "imza bekliyor"}</span>
                </div>
              </header>

              <div className="message-stream">
                {(userProfile?.interests?.length || userProfile?.bio) ? (
                  <article className="user-profile-hint">
                    <strong>Senin profil notların</strong>
                    {userProfile?.interests?.length ? <p>İlgi alanların: {userProfile.interests.join(" • ")}</p> : null}
                    {userProfile?.bio ? <p>Notun: {userProfile.bio}</p> : null}
                  </article>
                ) : null}
                {activeChat.messages.map((message) => (
                  <article
                    key={message.id}
                    className={message.sender === "user" ? "bubble user" : "bubble assistant"}
                  >
                    {message.kind === "image" ? (
                      <>
                        <p>{message.text}</p>
                        <img
                          className="chat-image zoomable-image"
                          src={message.image_url}
                          alt="shared visual"
                          onClick={() => onOpenImage(message.image_url, activeChat.profile.name)}
                        />
                      </>
                    ) : (
                      <p>{message.text}</p>
                    )}
                  </article>
                ))}
              </div>

              <footer className="composer">
                {!isChatSigned ? (
                  <div className="signature-warning">
                    Bu sohbeti devam ettirmek için önce MetaMask ile imzalaman gerekiyor.
                  </div>
                ) : null}
                <textarea
                  value={messageInput}
                  onChange={(event) => setMessageInput(event.target.value)}
                  placeholder="Mesajın burada... her gönderim 25 kredi."
                  disabled={!isChatSigned || isSending}
                />
                <button
                  className="primary-button"
                  onClick={isChatSigned ? onSend : onRequireSignature}
                  disabled={isSending}
                >
                  {isSending ? "Gönderiliyor..." : "Mesaj gönder"}
                </button>
              </footer>
            </>
          ) : (
            <div className="empty-card">
              <h2>Henüz aktif bir sohbet yok</h2>
              <p>Keşfet sayfasından sağa kaydır ve yeni bir AI persona ile eşleş.</p>
            </div>
          )}
        </section>
      </div>
    </section>
  );
}

export default function App() {
  const navigate = useNavigate();
  const [walletAddress, setWalletAddress] = useState("");
  const [config, setConfig] = useState(null);
  const [credits, setCredits] = useState(0);
  const [profiles, setProfiles] = useState([]);
  const [selfGender, setSelfGender] = useState("erkek");
  const [userProfile, setUserProfile] = useState({ interests: [], bio: "" });
  const [userInterestsInput, setUserInterestsInput] = useState("");
  const [userBioInput, setUserBioInput] = useState("");
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState("");
  const [messageInput, setMessageInput] = useState("");
  const [status, setStatus] = useState("Cüzdan bağlayıp keşfete başlayabilirsin.");
  const [isSending, setIsSending] = useState(false);
  const [drag, setDrag] = useState(initialDrag);
  const [provider, setProvider] = useState(null);
  const [signer, setSigner] = useState(null);
  const [signatureModal, setSignatureModal] = useState(null);
  const [isSigningChat, setIsSigningChat] = useState(false);
  const [lightboxImage, setLightboxImage] = useState(null);
  const dragState = useRef(initialDrag);

  const activeChat = chats.find((chat) => chat.id === activeChatId) || null;
  const topProfile = profiles[0] || null;

  async function refreshConfig() {
    const nextConfig = await fetchJson("/api/config");
    setConfig(nextConfig);
    return nextConfig;
  }

  async function refreshDiscover(address = walletAddress) {
    const query = address ? `?wallet_address=${encodeURIComponent(address)}` : "";
    const data = await fetchJson(`/api/discover${query}`);
    setProfiles(data.profiles);
    setCredits(data.credits);
    if (data.self_gender) {
      setSelfGender(data.self_gender);
    }
    if (data.profile) {
      setUserProfile(data.profile);
      setUserInterestsInput((data.profile.interests || []).join(", "));
      setUserBioInput(data.profile.bio || "");
    }
  }

  async function refreshChats(address = walletAddress) {
    if (!address) {
      return;
    }

    const data = await fetchJson(`/api/chats?wallet_address=${encodeURIComponent(address)}`);
    setChats(data.chats);
    setCredits(data.credits);
    if (data.profile) {
      setUserProfile(data.profile);
      setUserInterestsInput((data.profile.interests || []).join(", "));
      setUserBioInput(data.profile.bio || "");
    }

    if (!activeChatId && data.chats[0]) {
      setActiveChatId(data.chats[0].id);
    }
  }

  useEffect(() => {
    refreshConfig().catch(() => setStatus("Backend yapılandırması alınamadı."));
  }, []);

  useEffect(() => {
    if (!walletAddress) {
      return;
    }

    refreshDiscover(walletAddress).catch(() => setStatus("Keşfet verileri yüklenemedi."));
    refreshChats(walletAddress).catch(() => setStatus("Mesajlar yüklenemedi."));
  }, [walletAddress]);

  useEffect(() => {
    function handlePointerMove(event) {
      if (!dragState.current.active) {
        return;
      }

      const nextDeltaX = event.clientX - dragState.current.startX;
      dragState.current = { ...dragState.current, deltaX: nextDeltaX };
      setDrag(dragState.current);
    }

    function handlePointerUp() {
      if (!dragState.current.active) {
        return;
      }

      const finalDelta = dragState.current.deltaX;
      dragState.current = initialDrag;
      setDrag(initialDrag);

      if (finalDelta > 120) {
        handleSwipe("right");
      } else if (finalDelta < -120) {
        handleSwipe("left");
      }
    }

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };
  }, [topProfile, walletAddress]);

  async function connectWallet() {
    if (!window.ethereum) {
      setStatus("MetaMask bulunamadı.");
      return;
    }

    const browserProvider = new ethers.BrowserProvider(window.ethereum);
    const accounts = await browserProvider.send("eth_requestAccounts", []);
    const nextSigner = await browserProvider.getSigner();

    setProvider(browserProvider);
    setSigner(nextSigner);
    setWalletAddress(accounts[0]);

    const data = await fetchJson("/api/connect", {
      method: "POST",
      body: JSON.stringify({ wallet_address: accounts[0] })
    });

    setCredits(data.credits);
    if (data.self_gender) {
      setSelfGender(data.self_gender);
    }
    setUserProfile({
      interests: data.interests || [],
      bio: data.bio || ""
    });
    setUserInterestsInput((data.interests || []).join(", "));
    setUserBioInput(data.bio || "");
    setStatus("Cüzdan bağlandı. Profilleri keşfetmeye hazırsın.");
    navigate("/wallet");
  }

  async function updateSelfGender(nextGender) {
    if (!walletAddress) {
      setStatus("Önce cüzdan bağlayıp profil tercihini seçmelisin.");
      return;
    }

    const data = await fetchJson("/api/profile/self", {
      method: "POST",
      body: JSON.stringify({
        wallet_address: walletAddress,
        self_gender: nextGender
      })
    });

    setSelfGender(data.self_gender);
    setStatus(
      data.self_gender === "erkek"
        ? "Profil tercihin erkek olarak kaydedildi. Keşfette kadınlar gösteriliyor."
        : "Profil tercihin kadın olarak kaydedildi. Keşfette kaslı erkekler gösteriliyor."
    );
    setActiveChatId("");
    setProfiles([]);
    await refreshDiscover(walletAddress);
  }

  async function saveUserProfile() {
    if (!walletAddress) {
      setStatus("Önce cüzdan bağlayıp profil bilgilerini kaydetmelisin.");
      return;
    }

    const interests = userInterestsInput
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);

    const data = await fetchJson("/api/profile/preferences", {
      method: "POST",
      body: JSON.stringify({
        wallet_address: walletAddress,
        interests,
        bio: userBioInput
      })
    });

    setUserProfile(data.profile);
    setUserInterestsInput((data.profile.interests || []).join(", "));
    setUserBioInput(data.profile.bio || "");
    setStatus("Profil notların kaydedildi. Eşleşmeler artık buna göre sohbet açabilir.");
  }

  async function signMatchedChat(chat) {
    if (!window.ethereum || !walletAddress) {
      setStatus("Sohbet imzalamak için önce MetaMask bağlı olmalı.");
      return;
    }

    setIsSigningChat(true);
    try {
      const browserProvider = provider || new ethers.BrowserProvider(window.ethereum);
      const nextSigner = signer || (await browserProvider.getSigner());
      const signedMessage = buildChatSignatureMessage(chat, walletAddress);
      const signature = await nextSigner.signMessage(signedMessage);

      const data = await fetchJson(`/api/chats/${chat.id}/signature`, {
        method: "POST",
        body: JSON.stringify({
          wallet_address: walletAddress,
          signature,
          signed_message: signedMessage
        })
      });

      setChats((current) => current.map((item) => (item.id === chat.id ? data.chat : item)));
      setSignatureModal(null);
      setStatus(`${chat.profile.name} sohbeti imzalandı.`);
    } catch (error) {
      setStatus("Sohbet imzası alınamadı. Tekrar deneyebilirsin.");
    } finally {
      setIsSigningChat(false);
    }
  }

  function requireChatSignature(chat = activeChat) {
    if (!chat) {
      return;
    }

    setSignatureModal(chat);
    setStatus(`${chat.profile.name} ile yazışabilmek için önce sohbet imzalanmalı.`);
  }

  function openImageViewer(src, label) {
    setLightboxImage({ src, label });
  }

  async function ensureLocalChain() {
    if (!window.ethereum) {
      setStatus("Ağ değiştirmek için MetaMask gerekli.");
      return false;
    }

    try {
      await window.ethereum.request({
        method: "wallet_switchEthereumChain",
        params: [{ chainId: "0x7a6a" }]
      });
    } catch (switchError) {
      if (switchError.code === 4902) {
        await upsertLocalChain();
      } else {
        try {
          await upsertLocalChain();
        } catch (addError) {
          setStatus("Ağ değiştirme başarısız oldu.");
          return false;
        }
      }
    }

    try {
      await window.ethereum.request({
        method: "eth_blockNumber",
        params: []
      });
    } catch (probeError) {
      try {
        await upsertLocalChain();
        await window.ethereum.request({
          method: "wallet_switchEthereumChain",
          params: [{ chainId: "0x7a6a" }]
        });
        await window.ethereum.request({
          method: "eth_blockNumber",
          params: []
        });
      } catch (retryError) {
        setStatus("Local ağ RPC bağlantısı bozuk görünüyor. MetaMask'ta Monad Match Local ağını silip yeniden ekle.");
        return false;
      }
    }

    setStatus("Local Monad benzeri ağ aktif.");
    return true;
  }

  async function handleSwipe(direction) {
    if (!walletAddress) {
      setStatus("Sağa veya sola kaydırmak için önce MetaMask bağla.");
      navigate("/wallet");
      return;
    }

    if (!topProfile) {
      return;
    }

    const data = await fetchJson("/api/swipe", {
      method: "POST",
      body: JSON.stringify({
        wallet_address: walletAddress,
        profile_id: topProfile.id,
        direction
      })
    });

    setProfiles((current) => current.slice(1));

    if (data.matched && data.chat) {
      setChats((current) => [data.chat, ...current.filter((chat) => chat.id !== data.chat.id)]);
      setActiveChatId(data.chat.id);
      setSignatureModal(data.chat);
      setStatus(`${topProfile.name} ile sohbet açıldı.`);
      navigate("/messages");
    } else {
      setStatus(`${topProfile.name} sola kaydırıldı.`);
    }
  }

  useEffect(() => {
    if (!signatureModal || !walletAddress || isSigningChat) {
      return;
    }

    signMatchedChat(signatureModal);
  }, [signatureModal, walletAddress]);

  async function buyCredits() {
    if (!walletAddress) {
      setStatus("Kredi satın almak için önce cüzdan bağla.");
      return;
    }

    const nextConfig = config || (await refreshConfig());
    const contract = nextConfig?.contract;

    if (!contract || !window.ethereum) {
      const fallback = await fetchJson("/api/demo/topup", {
        method: "POST",
        body: JSON.stringify({ wallet_address: walletAddress, credits: 1000 })
      });
      setCredits(fallback.credits);
      setStatus("Kontrat hazır değil. Demo kredisi yüklendi.");
      return;
    }

    const switched = await ensureLocalChain();
    if (!switched) {
      return;
    }

    try {
      const browserProvider = provider || new ethers.BrowserProvider(window.ethereum);
      const nextSigner = signer || (await browserProvider.getSigner());
      const liveContract = new ethers.Contract(contract.address, contract.abi, nextSigner);
      let tx;

      try {
        tx = await liveContract.purchaseCredits({ value: ethers.parseEther("1") });
      } catch (error) {
        const message = String(error?.message || "").toLowerCase();
        const code = error?.code;

        if (
          code === "INSUFFICIENT_FUNDS" ||
          message.includes("insufficient funds") ||
          message.includes("not enough funds") ||
          message.includes("exceeds balance")
        ) {
          await fetchJson("/api/dev/fund-wallet", {
            method: "POST",
            body: JSON.stringify({ wallet_address: walletAddress })
          });
          setStatus("Local ağ için 5 MON faucet yüklendi. Satın alma tekrar deneniyor...");
          tx = await liveContract.purchaseCredits({ value: ethers.parseEther("1") });
        } else {
          throw error;
        }
      }

      await tx.wait();

      const claim = await fetchJson("/api/credits/claim", {
        method: "POST",
        body: JSON.stringify({
          wallet_address: walletAddress,
          tx_hash: tx.hash
        })
      });

      setCredits(claim.credits);
      setStatus(`1 MON ödemesi alındı. ${claim.credits_granted} kredi hesabına tanımlandı.`);
    } catch (error) {
      setStatus(error.message || "Kredi satın alma başarısız oldu.");
    }
  }

  async function sendMessage() {
    if (!walletAddress || !activeChat || !messageInput.trim()) {
      return;
    }

    if (!activeChat.signature) {
      requireChatSignature(activeChat);
      return;
    }

    setIsSending(true);
    let timeoutId;
    try {
      const controller = new AbortController();
      timeoutId = window.setTimeout(() => controller.abort(), 20000);
      const data = await fetchJson(`/api/chats/${activeChat.id}/message`, {
        method: "POST",
        signal: controller.signal,
        body: JSON.stringify({
          wallet_address: walletAddress,
          message: messageInput.trim()
        })
      });

      setChats((current) => current.map((chat) => (chat.id === activeChat.id ? data.chat : chat)));
      setCredits(data.credits);
      setMessageInput("");
      setStatus(`Mesaj gönderildi. ${data.message_cost} kredi harcandı.`);
    } catch (error) {
      if (error.name === "AbortError") {
        setStatus("Yanıt çok uzadı, lütfen tekrar dene.");
      } else {
        if (error.message?.includes("imzalamadan")) {
          requireChatSignature(activeChat);
        }
        setStatus(error.message || "Mesaj gönderilemedi.");
      }
    } finally {
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
      setIsSending(false);
    }
  }

  return (
    <main className="app-shell routed-shell">
      <aside className="sidebar">
        <div>
          <p className="eyebrow">Monad Match</p>
          <h1>Swipe, eşleş, yazış ve krediyi zincire taşı.</h1>
          <p className="lead">
            Artık tüm bölümler farklı sayfalarda. Profil, keşfet, mesajlar ve cüzdan akışları ayrı route olarak
            çalışıyor.
          </p>
        </div>

        <div className="sidebar-summary">
          <span className="label">Bagli hesap</span>
          <strong>{shortAddress(walletAddress)}</strong>
          <span className="tiny-text">Kredi: {credits}</span>
        </div>

        <nav className="route-nav">
          <NavLink className={({ isActive }) => (isActive ? "route-link active" : "route-link")} to="/profile">
            Profil
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? "route-link active" : "route-link")} to="/discover">
            Keşfet
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? "route-link active" : "route-link")} to="/messages">
            Mesajlar
          </NavLink>
          <NavLink className={({ isActive }) => (isActive ? "route-link active" : "route-link")} to="/wallet">
            Cüzdan Bağla
          </NavLink>
        </nav>

        <p className="tiny-text">Durum: {status}</p>
      </aside>

      <section className="content-panel">
        <Routes>
          <Route path="/" element={<Navigate to="/profile" replace />} />
          <Route
            path="/profile"
            element={
              <ProfilePage
                walletAddress={walletAddress}
                credits={credits}
                chats={chats}
                config={config}
                status={status}
                selfGender={selfGender}
                userInterestsInput={userInterestsInput}
                setUserInterestsInput={setUserInterestsInput}
                userBioInput={userBioInput}
                setUserBioInput={setUserBioInput}
                onChangeSelfGender={updateSelfGender}
                onSaveProfile={saveUserProfile}
              />
            }
          />
          <Route
            path="/discover"
            element={
              <DiscoverPage
                walletAddress={walletAddress}
                profiles={profiles}
                drag={drag}
                onPointerDown={(event) => {
                  dragState.current = { active: true, startX: event.clientX, deltaX: 0 };
                  setDrag(dragState.current);
                }}
                onSwipe={handleSwipe}
                onRefresh={refreshDiscover}
                onGoWallet={() => navigate("/wallet")}
                onOpenImage={openImageViewer}
              />
            }
          />
          <Route
            path="/messages"
            element={
              <MessagesPage
                chats={chats}
                activeChatId={activeChatId}
                setActiveChatId={setActiveChatId}
                activeChat={activeChat}
              config={config}
              messageInput={messageInput}
                setMessageInput={setMessageInput}
                isSending={isSending}
                onSend={sendMessage}
                onRequireSignature={() => requireChatSignature(activeChat)}
                onOpenImage={openImageViewer}
                userProfile={userProfile}
              />
            }
          />
          <Route
            path="/wallet"
            element={
              <WalletPage
                walletAddress={walletAddress}
                credits={credits}
                config={config}
                status={status}
                onConnect={connectWallet}
              />
            }
          />
        </Routes>
      </section>

      {signatureModal ? (
        <div className="modal-backdrop" onClick={() => !isSigningChat && setSignatureModal(null)}>
          <div className="signature-modal" onClick={(event) => event.stopPropagation()}>
            <p className="eyebrow">Sohbet İmzası</p>
            <h2>{signatureModal.profile.name} ile sohbet açıldı</h2>
            <p>
              Bu eşleşmeyi onaylamak için MetaMask üzerinden bu sohbeti imzalaman gerekiyor. İmza alındığında sohbet
              aktif olarak işaretlenecek.
            </p>
            <div className="signature-box">
              <span>İmzalanacak sohbet</span>
              <strong>{signatureModal.id}</strong>
            </div>
            <div className="action-row">
              <button className="primary-button" onClick={() => signMatchedChat(signatureModal)} disabled={isSigningChat}>
                {isSigningChat ? "İmza bekleniyor..." : "Şimdi imzala"}
              </button>
              <button className="ghost-button" onClick={() => setSignatureModal(null)} disabled={isSigningChat}>
                Sonra
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {lightboxImage ? (
        <div className="modal-backdrop" onClick={() => setLightboxImage(null)}>
          <div className="image-lightbox" onClick={(event) => event.stopPropagation()}>
            <img src={lightboxImage.src} alt={lightboxImage.label} />
          </div>
        </div>
      ) : null}
    </main>
  );
}
