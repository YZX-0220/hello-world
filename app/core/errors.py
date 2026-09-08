"""统一错误体系。

错误响应格式（接口说明 1.7 节）：
{
  "error": {
    "code": "PROJECT_VERSION_CONFLICT",
    "message": "...",
    "request_id": "uuid",
    "details": {}
  }
}
detail 只包含安全、可公开的字段错误，绝不返回堆栈/厂商原始响应/密钥。
"""

from collections.abc import Mapping
from typing import Any, ClassVar

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response


class ErrorCode(str):
    """错误码字符串常量 + 默认 HTTP 状态码与中文说明的中枢。

    使用字符串子类以便直接比较，同时通过 __new__ 登记默认状态码/消息。
    """

    _INFO: ClassVar[dict[str, tuple[int, str]]] = {}

    def __new__(cls, value: str, status_code: int, message: str) -> "ErrorCode":
        obj = str.__new__(cls, value)
        cls._INFO[value] = (status_code, message)
        return obj

    @property
    def status_code(self) -> int:
        return self._INFO.get(self, (500, "服务器内部错误"))[0]

    @property
    def message(self) -> str:
        return self._INFO.get(self, (500, "服务器内部错误"))[1]


# ---- 认证与限流 ----
AUTH_REQUIRED = ErrorCode("AUTH_REQUIRED", 401, "需要登录")
SESSION_EXPIRED = ErrorCode("SESSION_EXPIRED", 401, "登录已过期")
CSRF_INVALID = ErrorCode("CSRF_INVALID", 403, "防跨站令牌无效")
INVALID_CREDENTIALS = ErrorCode("INVALID_CREDENTIALS", 401, "邮箱或密码错误")
EMAIL_CODE_INVALID = ErrorCode("EMAIL_CODE_INVALID", 400, "验证码错误")
EMAIL_CODE_EXPIRED = ErrorCode("EMAIL_CODE_EXPIRED", 400, "验证码已过期")
EMAIL_CODE_ATTEMPTS_EXCEEDED = ErrorCode("EMAIL_CODE_ATTEMPTS_EXCEEDED", 429, "验证码尝试次数过多")
RATE_LIMITED = ErrorCode("RATE_LIMITED", 429, "操作过于频繁")
EMAIL_DELIVERY_UNAVAILABLE = ErrorCode("EMAIL_DELIVERY_UNAVAILABLE", 503, "邮件暂时无法发送")
EMAIL_ALREADY_REGISTERED = ErrorCode("EMAIL_ALREADY_REGISTERED", 409, "该邮箱已注册，请直接登录")

# ---- 对话与 Agent ----
CONVERSATION_NOT_FOUND = ErrorCode("CONVERSATION_NOT_FOUND", 404, "对话不存在或无权访问")
CONVERSATION_BUSY = ErrorCode("CONVERSATION_BUSY", 409, "对话正在处理上一条消息")
MESSAGE_TOO_LONG = ErrorCode("MESSAGE_TOO_LONG", 413, "消息过长")
IDEMPOTENCY_KEY_REUSED = ErrorCode("IDEMPOTENCY_KEY_REUSED", 409, "同一幂等编号被不同请求使用")
TEXT_PROVIDER_TIMEOUT = ErrorCode("TEXT_PROVIDER_TIMEOUT", 504, "文本模型响应超时")
TEXT_PROVIDER_UNAVAILABLE = ErrorCode("TEXT_PROVIDER_UNAVAILABLE", 502, "文本模型暂时不可用")
AGENT_OUTPUT_INVALID = ErrorCode("AGENT_OUTPUT_INVALID", 502, "AI 结构化输出无法校验")
PROJECT_VERSION_CONFLICT = ErrorCode("PROJECT_VERSION_CONFLICT", 409, "视频方案已经发生变化，请刷新后重新确认")
PROJECT_NOT_READY = ErrorCode("PROJECT_NOT_READY", 422, "视频方案信息不足")

# ---- 视频配置与素材 ----
VIDEO_PROTOCOL_UNSUPPORTED = ErrorCode("VIDEO_PROTOCOL_UNSUPPORTED", 422, "协议未实现或未启用")
VIDEO_TEMPLATE_UNSUPPORTED = ErrorCode("VIDEO_TEMPLATE_UNSUPPORTED", 422, "协议模板不可用")
VIDEO_MODEL_UNSUPPORTED = ErrorCode("VIDEO_MODEL_UNSUPPORTED", 422, "模型未登记或不允许")
VIDEO_CONFIG_INVALID = ErrorCode("VIDEO_CONFIG_INVALID", 422, "视频接口配置无效")
VIDEO_API_CONFIG_NOT_FOUND = ErrorCode("VIDEO_API_CONFIG_NOT_FOUND", 404, "视频接口配置不存在或无权访问")
VIDEO_CONFIG_NAME_EXISTS = ErrorCode("VIDEO_CONFIG_NAME_EXISTS", 409, "该配置名称已存在")
RELAY_RISK_NOT_ACCEPTED = ErrorCode("RELAY_RISK_NOT_ACCEPTED", 422, "未确认第三方中转风险")
UNSAFE_BASE_URL = ErrorCode("UNSAFE_BASE_URL", 422, "接口地址存在安全风险")
ASSET_NOT_FOUND = ErrorCode("ASSET_NOT_FOUND", 404, "素材不存在或无权访问")
ASSET_TYPE_UNSUPPORTED = ErrorCode("ASSET_TYPE_UNSUPPORTED", 415, "文件类型不支持")
ASSET_TOO_LARGE = ErrorCode("ASSET_TOO_LARGE", 413, "文件超过限制")
ASSET_CONTENT_INVALID = ErrorCode("ASSET_CONTENT_INVALID", 422, "文件内容损坏或伪装类型")
ASSET_IN_USE = ErrorCode("ASSET_IN_USE", 409, "素材仍被任务使用")

# ---- 视频任务 ----
PROJECT_NOT_CONFIRMED = ErrorCode("PROJECT_NOT_CONFIRMED", 409, "当前方案尚未确认")
VIDEO_MODE_UNSUPPORTED = ErrorCode("VIDEO_MODE_UNSUPPORTED", 422, "模型不支持所选模式")
VIDEO_INPUT_INVALID = ErrorCode("VIDEO_INPUT_INVALID", 422, "视频任务输入组合错误")
VIDEO_OPTION_UNSUPPORTED = ErrorCode("VIDEO_OPTION_UNSUPPORTED", 422, "生成选项不受支持")
VIDEO_SUBMISSION_FAILED = ErrorCode("VIDEO_SUBMISSION_FAILED", 502, "厂商明确拒绝任务")
PROVIDER_SUBMISSION_UNKNOWN = ErrorCode("PROVIDER_SUBMISSION_UNKNOWN", 202, "无法确认厂商是否已接受")
VIDEO_PROVIDER_RATE_LIMITED = ErrorCode("VIDEO_PROVIDER_RATE_LIMITED", 429, "厂商限制请求频率")
VIDEO_POLL_FAILED = ErrorCode("VIDEO_POLL_FAILED", 502, "查询厂商状态暂时失败")
VIDEO_CANCEL_UNSUPPORTED = ErrorCode("VIDEO_CANCEL_UNSUPPORTED", 409, "厂商不支持取消")
VIDEO_RESULT_EXPIRED = ErrorCode("VIDEO_RESULT_EXPIRED", 410, "厂商结果已经过期")
VIDEO_DOWNLOAD_FAILED = ErrorCode("VIDEO_DOWNLOAD_FAILED", 502, "结果保存到本站失败")


class FieldError(BaseModel):
    """字段校验错误项（接口说明 1.7 节 details.field_errors）。"""

    field: str
    reason: str


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


class AppError(Exception):
    """业务异常，携带统一错误码、可覆盖说明与安全 details。"""

    def __init__(
        self,
        code: ErrorCode,
        message: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.code = str(code)
        self.status_code: int = code.status_code
        self.message = message or code.message
        self.details: dict[str, Any] = dict(details or {})
        super().__init__(self.message)


def build_error(request: Request, code: str, message: str, details: Mapping[str, Any]) -> ErrorResponse:
    """按统一格式构造错误响应，并回填 request_id。"""
    request_id = getattr(request.state, "request_id", None) or "-"
    return ErrorResponse(
        error=ErrorBody(code=code, message=message, request_id=request_id, details=dict(details or {}))
    )


def _request_id(request: Request) -> str:
    """从请求状态读取中间件写入的 request_id，取不到时回退占位符。"""
    return getattr(request.state, "request_id", None) or "-"


def _to_json_response(status_code: int, request_id: str, code: str, message: str, details: Mapping[str, Any]) -> Response:
    """构造统一的 JSON 错误响应。"""
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error=ErrorBody(code=code, message=message, request_id=request_id, details=dict(details))
        ).model_dump(),
    )


def _app_error_handler(request: Request, exc: AppError) -> Response:
    return _to_json_response(exc.status_code, _request_id(request), exc.code, exc.message, exc.details)


def _validation_error_handler(request: Request, exc: RequestValidationError) -> Response:
    """把 Pydantic/FastAPI 字段校验错误转成统一格式，塞进 details.field_errors。"""
    field_errors: list[dict[str, str]] = []
    for err in exc.errors():
        field = ".".join(str(p) for p in err.get("loc", []) if p not in ("body", "query", "path"))
        field_errors.append(FieldError(field=field or "_root", reason=str(err.get("msg", ""))).model_dump())
    return _to_json_response(422, _request_id(request), "VALIDATION_ERROR", "请求参数校验失败", {"field_errors": field_errors})


def _http_error_handler(request: Request, exc: StarletteHTTPException) -> Response:
    """把任意 HTTP 异常转成统一格式，避免泄露内部信息。"""
    message = exc.detail if isinstance(exc.detail, str) else "请求出错"
    return _to_json_response(exc.status_code, _request_id(request), "HTTP_ERROR", message, {})


def _unhandled_error_handler(request: Request, exc: Exception) -> Response:
    """兜底处理器：绝不向客户端泄露堆栈或内部细节。"""
    return _to_json_response(500, _request_id(request), "INTERNAL_ERROR", "服务器内部错误", {})


def register_exception_handlers(app: FastAPI) -> None:
    """注册全部异常处理器。"""
    # 说明：Starlette 对异常处理回调的泛型签名要求统一为 (Request, Exception)，
    # 此处回调参数为各具体异常类型，属框架泛型限制，故忽略 arg-type 类型告警。
    app.add_exception_handler(AppError, _app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, _http_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_error_handler)
