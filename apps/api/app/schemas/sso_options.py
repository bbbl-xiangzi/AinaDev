"""Typed, bounded OAuth2 connection options. No executable mapping expressions."""
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class OAuthOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token_method: Literal["GET", "POST", "PUT"] = "POST"
    token_mode: Literal["query", "form", "json"] = "form"
    token_auth: Literal["parameters", "basic"] = "parameters"
    userinfo_source: Literal["endpoint", "token"] = "endpoint"
    userinfo_method: Literal["GET", "POST", "PUT"] = "GET"
    userinfo_mode: Literal["bearer", "query", "form", "json"] = "bearer"
    pkce: bool = False
    authorize_params: dict[str, str] = Field(default_factory=dict)
    token_params: dict[str, str] = Field(default_factory=dict)
    access_token_param: str = "access_token"
    userinfo_path: str = ""
    claim_username: str = "loginName"
    claim_mobile: str = "mobile"
    subject_mode: Literal["string", "single_array"] = "string"
    logout_url: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def validate_options(self):
        groups = [(self.authorize_params, {"client_id","redirect_uri","response_type","scope","state","code_challenge","code_challenge_method"}),
                  (self.token_params, {"client_id","client_secret","grant_type","code","redirect_uri","code_verifier"})]
        for mappings, allowed in groups:
            if set(mappings) - allowed:
                raise ValueError("存在不支持的 OAuth2 参数")
            names = [mappings.get(key,key) for key in allowed]
            if len(set(names)) != len(names) or any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,63}",name) for name in names):
                raise ValueError("参数名无效或重复")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,63}",self.access_token_param):
            raise ValueError("access_token 参数名无效")
        for path in (self.userinfo_path,self.claim_username,self.claim_mobile):
            if len(path)>200 or (path and not re.fullmatch(r"[\w-]+(?:\.[\w-]+)*",path)):
                raise ValueError("字段路径仅支持以点分隔的对象字段")
        if self.token_method == "GET" and self.token_mode != "query":
            raise ValueError("GET Token 请求必须使用 Query")
        if self.userinfo_method == "GET" and self.userinfo_mode not in {"query","bearer"}:
            raise ValueError("GET 用户信息请求仅支持 Query 或 Bearer")
        return self
