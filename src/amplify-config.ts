import { Amplify } from "aws-amplify";

/**
 * Amplify v6 の設定
 *
 * ★ リダイレクトループを避けるポイント:
 *   1. redirectSignIn / redirectSignOut は Cognito App Client の callbackUrls / logoutUrls と完全一致させる
 *   2. 末尾スラッシュの有無も一致させる（"http://localhost:3000/" ← スラッシュあり）
 *   3. responseType は "code"（Authorization Code + PKCE）を使う
 */
export function configureAmplify() {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: import.meta.env.VITE_USER_POOL_ID,
        userPoolClientId: import.meta.env.VITE_USER_POOL_CLIENT_ID,
        loginWith: {
          oauth: {
            domain: import.meta.env.VITE_COGNITO_DOMAIN,
            scopes: ["openid", "email", "profile"],
            redirectSignIn: ["http://localhost:3000/"],
            redirectSignOut: ["http://localhost:3000/"],
            responseType: "code",
          },
        },
      },
    },
  });
}
