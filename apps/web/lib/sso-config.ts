export const oauthDefaults = {
  token_method: "POST", token_mode: "form", token_auth: "parameters",
  userinfo_source: "endpoint", userinfo_method: "GET", userinfo_mode: "bearer",
  pkce: false, authorize_params: {} as Record<string, string>, token_params: {} as Record<string, string>,
  access_token_param: "access_token", userinfo_path: "", claim_username: "loginName",
  claim_mobile: "mobile", subject_mode: "string", logout_url: "",
};

export function applyDecPreset(cfg: any) {
  return { ...cfg, enabled: false, protocol: "oauth2", label: "东方电气统一身份登录",
    issuer: "", jwks_uri: "", scopes: "", bind_rule: "sub", extract_employee: false,
    authorization_endpoint: "https://iam.dongfang.com/idp/oauth2/authorize",
    token_endpoint: "https://iam.dongfang.com/idp/oauth2/getToken",
    userinfo_endpoint: `https://iam.dongfang.com/idp/oauth2/getUserInfo${cfg.client_id ? `?client_id=${encodeURIComponent(cfg.client_id)}` : ""}`,
    claim_sub: "spRoleList", claim_name: "displayName", claim_email: "mail",
    oauth_options: { ...oauthDefaults, token_mode: "query", userinfo_mode: "query", subject_mode: "single_array" },
  };
}

export function ssoPayload(cfg: any, secret: string) {
  const keys = ["enabled","protocol","label","issuer","client_id","authorization_endpoint","token_endpoint",
    "jwks_uri","userinfo_endpoint","scopes","bind_rule","auto_provision","extract_employee","claim_sub","claim_email","claim_name"];
  const payload: Record<string, any> = Object.fromEntries(keys.map(key=>[key,cfg[key] ?? ""]));
  payload.client_secret = secret || null;
  payload.oauth_options = { ...oauthDefaults, ...cfg.oauth_options };
  return payload;
}
