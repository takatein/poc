#!/usr/bin/env node
import "source-map-support/register";
import * as cdk from "aws-cdk-lib";
import { GoogleAuthStack } from "../lib/google-auth-stack";

const app = new cdk.App();

new GoogleAuthStack(app, "GoogleAuthPocStack", {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION ?? "ap-northeast-1",
  },
});
