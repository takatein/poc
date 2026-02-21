import { useState, useEffect } from "react";
import {
  signInWithRedirect,
  signOut,
  getCurrentUser,
  fetchAuthSession,
  fetchUserAttributes,
} from "aws-amplify/auth";
import { Hub } from "aws-amplify/utils";

type AuthState = "loading" | "signedIn" | "signedOut";

interface UserInfo {
  username: string;
  email?: string;
  name?: string;
  picture?: string;
}

export default function App() {
  const [authState, setAuthState] = useState<AuthState>("loading");
  const [user, setUser] = useState<UserInfo | null>(null);
  const [tokens, setTokens] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // 認証状態を確認
  const checkAuth = async () => {
    try {
      const currentUser = await getCurrentUser();
      const attributes = await fetchUserAttributes();
      const session = await fetchAuthSession();

      setUser({
        username: currentUser.username,
        email: attributes.email,
        name: [attributes.given_name, attributes.family_name]
          .filter(Boolean)
          .join(" "),
        picture: attributes.picture,
      });

      // デバッグ用：トークン情報を表示
      setTokens(
        JSON.stringify(
          {
            idToken: session.tokens?.idToken?.toString().slice(0, 50) + "...",
            accessToken:
              session.tokens?.accessToken?.toString().slice(0, 50) + "...",
            expiration: session.tokens?.idToken?.payload?.exp
              ? new Date(
                  (session.tokens.idToken.payload.exp as number) * 1000
                ).toISOString()
              : "N/A",
          },
          null,
          2
        )
      );

      setAuthState("signedIn");
    } catch {
      setAuthState("signedOut");
      setUser(null);
      setTokens(null);
    }
  };

  useEffect(() => {
    checkAuth();

    // Hub リスナーで認証イベントを監視
    const unsubscribe = Hub.listen("auth", ({ payload }) => {
      console.log("[Auth Event]", payload.event, payload);
      switch (payload.event) {
        case "signInWithRedirect":
          checkAuth();
          break;
        case "signInWithRedirect_failure":
          setError(`認証エラー: ${JSON.stringify(payload.data)}`);
          setAuthState("signedOut");
          break;
      }
    });

    return unsubscribe;
  }, []);

  const handleSignIn = () => {
    signInWithRedirect({ provider: "Google" });
  };

  const handleSignOut = async () => {
    await signOut();
    setAuthState("signedOut");
    setUser(null);
    setTokens(null);
  };

  return (
    <div style={styles.container}>
      <h1 style={styles.title}>AWS Google Auth PoC</h1>
      <p style={styles.subtitle}>Cognito + Google OAuth 動作確認</p>

      {error && (
        <div style={styles.errorBox}>
          <strong>Error:</strong> {error}
          <button onClick={() => setError(null)} style={styles.dismissBtn}>
            ✕
          </button>
        </div>
      )}

      {authState === "loading" && <p>認証状態を確認中...</p>}

      {authState === "signedOut" && (
        <div style={styles.card}>
          <p>ログインしていません</p>
          <button onClick={handleSignIn} style={styles.googleBtn}>
            Google でログイン
          </button>
        </div>
      )}

      {authState === "signedIn" && user && (
        <div style={styles.card}>
          <h2>ログイン成功!</h2>
          <div style={styles.userInfo}>
            {user.picture && (
              <img
                src={user.picture}
                alt="avatar"
                style={styles.avatar}
                referrerPolicy="no-referrer"
              />
            )}
            <div>
              <p>
                <strong>Name:</strong> {user.name || "N/A"}
              </p>
              <p>
                <strong>Email:</strong> {user.email || "N/A"}
              </p>
              <p>
                <strong>Username:</strong> {user.username}
              </p>
            </div>
          </div>

          <details style={styles.details}>
            <summary>Token Info (debug)</summary>
            <pre style={styles.pre}>{tokens}</pre>
          </details>

          <button onClick={handleSignOut} style={styles.signOutBtn}>
            ログアウト
          </button>
        </div>
      )}

      <footer style={styles.footer}>
        <details>
          <summary>認証フロー図</summary>
          <pre style={styles.flowChart}>{`
  [ブラウザ]
     │
     │ 1. "Googleでログイン" クリック
     ▼
  [Cognito Hosted UI]
     │
     │ 2. Google へリダイレクト
     ▼
  [Google OAuth]
     │
     │ 3. ユーザーが認証・同意
     ▼
  [Cognito Callback]
     │
     │ 4. Authorization Code 発行
     ▼
  [ブラウザ localhost:3000/]
     │
     │ 5. Amplify が Code → Token 交換
     ▼
  [ログイン完了!]
          `}</pre>
        </details>
      </footer>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: 600,
    margin: "40px auto",
    padding: "0 20px",
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  title: {
    marginBottom: 4,
  },
  subtitle: {
    color: "#666",
    marginTop: 0,
  },
  card: {
    border: "1px solid #ddd",
    borderRadius: 8,
    padding: 24,
    marginTop: 20,
  },
  googleBtn: {
    padding: "12px 24px",
    fontSize: 16,
    backgroundColor: "#4285F4",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    cursor: "pointer",
  },
  signOutBtn: {
    marginTop: 16,
    padding: "8px 16px",
    fontSize: 14,
    backgroundColor: "#dc3545",
    color: "#fff",
    border: "none",
    borderRadius: 4,
    cursor: "pointer",
  },
  userInfo: {
    display: "flex",
    alignItems: "center",
    gap: 16,
    marginBottom: 16,
  },
  avatar: {
    width: 64,
    height: 64,
    borderRadius: "50%",
  },
  details: {
    marginTop: 16,
  },
  pre: {
    backgroundColor: "#f5f5f5",
    padding: 12,
    borderRadius: 4,
    fontSize: 12,
    overflow: "auto",
  },
  errorBox: {
    backgroundColor: "#f8d7da",
    color: "#842029",
    padding: "12px 16px",
    borderRadius: 4,
    marginTop: 16,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  dismissBtn: {
    background: "none",
    border: "none",
    fontSize: 18,
    cursor: "pointer",
    color: "#842029",
  },
  footer: {
    marginTop: 40,
    color: "#888",
    fontSize: 14,
  },
  flowChart: {
    fontSize: 13,
    lineHeight: 1.4,
  },
};
