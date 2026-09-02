ADMIN_PERMISSIONS: list[tuple[str, str, str, str]] = [
    ("scheduler:read", "스케줄 조회", "scheduler", "admin"),
    ("scheduler:manage", "스케줄 생성·수정·실행", "scheduler", "admin"),
    ("task:read", "작업 상태 조회", "task", "admin"),
    ("task:cancel", "작업 취소·재시도", "task", "admin"),
    ("user:read", "사용자 목록 조회", "user", "admin"),
    ("user:manage", "사용자 생성·비활성화", "user", "admin"),
    ("role:manage", "역할 부여·권한 변경", "user", "admin"),
    ("audit:read", "감사 로그 조회", "audit", "admin"),
]

ROLE_ADMIN = "admin"
ROLE_OPERATOR = "operator"

ROLE_PERMISSIONS: dict[str, list[str]] = {
    ROLE_ADMIN: [code for code, *_ in ADMIN_PERMISSIONS],
    ROLE_OPERATOR: [
        "scheduler:read",
        "scheduler:manage",
        "task:read",
        "task:cancel",
    ],
}
