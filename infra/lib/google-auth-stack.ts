import * as cdk from "aws-cdk-lib";
import * as cognito from "aws-cdk-lib/aws-cognito";
import { Construct } from "constructs";

export class GoogleAuthStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // --- Google OAuth クレデンシャル（デプロイ時にコンテキストから取得） ---
    const googleClientId = this.node.tryGetContext("googleClientId");
    const googleClientSecret = this.node.tryGetContext("googleClientSecret");

    if (!googleClientId || !googleClientSecret) {
      throw new Error(
        "Google OAuth credentials required. Deploy with:\n" +
          '  cdk deploy -c googleClientId="xxx" -c googleClientSecret="yyy"'
      );
    }

    // --- Cognito User Pool ---
    const userPool = new cognito.UserPool(this, "UserPool", {
      userPoolName: "google-auth-poc-pool",
      selfSignUpEnabled: false, // Google経由のみ許可
      signInAliases: { email: true },
      autoVerify: { email: true },
      standardAttributes: {
        email: { required: true, mutable: true },
      },
      removalPolicy: cdk.RemovalPolicy.DESTROY, // PoC用：スタック削除時にプールも削除
    });

    // --- Google Identity Provider ---
    const googleProvider = new cognito.UserPoolIdentityProviderGoogle(
      this,
      "GoogleProvider",
      {
        userPool,
        clientId: googleClientId,
        clientSecretValue: cdk.SecretValue.unsafePlainText(googleClientSecret),
        scopes: ["openid", "email", "profile"],
        attributeMapping: {
          email: cognito.ProviderAttribute.GOOGLE_EMAIL,
          givenName: cognito.ProviderAttribute.GOOGLE_GIVEN_NAME,
          familyName: cognito.ProviderAttribute.GOOGLE_FAMILY_NAME,
          profilePicture: cognito.ProviderAttribute.GOOGLE_PICTURE,
        },
      }
    );

    // --- Cognito Domain（Hosted UI用） ---
    const domainPrefix = `google-auth-poc-${cdk.Aws.ACCOUNT_ID}`;
    const userPoolDomain = userPool.addDomain("CognitoDomain", {
      cognitoDomain: { domainPrefix },
    });

    // --- App Client ---
    // ★ ポイント: callbackUrls / logoutUrls を正確に設定することがリダイレクトループ回避の鍵
    const userPoolClient = userPool.addClient("WebClient", {
      userPoolClientName: "google-auth-poc-web",
      generateSecret: false, // SPAなのでシークレット不要
      oAuth: {
        flows: {
          authorizationCodeGrant: true, // Authorization Code + PKCE
        },
        scopes: [
          cognito.OAuthScope.OPENID,
          cognito.OAuthScope.EMAIL,
          cognito.OAuthScope.PROFILE,
        ],
        callbackUrls: [
          "http://localhost:3000/", // ★ ローカル開発用。末尾スラッシュに注意！
        ],
        logoutUrls: [
          "http://localhost:3000/", // ★ ログアウト後のリダイレクト先
        ],
      },
      supportedIdentityProviders: [
        cognito.UserPoolClientIdentityProvider.GOOGLE,
      ],
    });

    // Google Provider が作成されてから Client を作る依存関係を明示
    userPoolClient.node.addDependency(googleProvider);

    // --- Outputs ---
    new cdk.CfnOutput(this, "UserPoolId", {
      value: userPool.userPoolId,
      description: "Cognito User Pool ID → VITE_USER_POOL_ID",
    });

    new cdk.CfnOutput(this, "UserPoolClientId", {
      value: userPoolClient.userPoolClientId,
      description: "Cognito App Client ID → VITE_USER_POOL_CLIENT_ID",
    });

    new cdk.CfnOutput(this, "CognitoDomain", {
      value: `${domainPrefix}.auth.${this.region}.amazoncognito.com`,
      description: "Cognito Hosted UI Domain → VITE_COGNITO_DOMAIN",
    });
  }
}
