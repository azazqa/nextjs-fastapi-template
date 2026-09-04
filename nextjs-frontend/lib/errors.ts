import type {
  AuthJwtLoginError,
  ResetForgotPasswordError,
  ResetResetPasswordError,
} from "@/app/clientService";

type ClientApiError =
  | AuthJwtLoginError
  | ResetForgotPasswordError
  | ResetResetPasswordError;

export function getErrorMessage(error: ClientApiError): string {
  let errorMessage = "An unknown error occurred";

  const detail = error.detail;
  if (typeof detail === "string") {
    errorMessage = detail;
  } else if (Array.isArray(detail) && detail.length > 0) {
    const parts = detail
      .map((d) => (d && typeof d === "object" && "msg" in d ? String(d.msg) : ""))
      .filter(Boolean);
    if (parts.length > 0) {
      errorMessage = parts.join("; ");
    }
  } else if (typeof detail === "object" && detail !== null && "reason" in detail) {
    errorMessage = String((detail as { reason: string }).reason);
  }

  return errorMessage;
}
