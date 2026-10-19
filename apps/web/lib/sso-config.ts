export const oauthDefaults = {
  token_method: "POST", token_mode: "form", token_auth: "parameters",
  userinfo_source: "endpoint", userinfo_method: "GET", userinfo_mode: "bearer",
  pkce: false, authorize_params: {} as Record<string, string>, token_params: {} as Record<string, string>,
  access_token_param: "access_token", userinfo_path: "", claim_username: "preferred_username",
  claim_mobile: "phone_number", subject_mode: "string", logout_url: "",
};

export function ssoPayload(cfg: any, secret: string) {
  const keys = ["enabled","protocol","label","issuer","client_id","authorization_endpoint","token_endpoint",
    "jwks_uri","userinfo_endpoint","scopes","bind_rule","auto_provision","extract_employee","claim_sub","claim_email","claim_name"];
  const payload: Record<string, any> = Object.fromEntries(keys.map(key=>[key,cfg[key] ?? ""]));
  payload.client_secret = secret || null;
  payload.oauth_options = { ...oauthDefaults, ...cfg.oauth_options };
  return payload;
}
