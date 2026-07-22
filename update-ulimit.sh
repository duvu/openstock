#!/usr/bin/env bash
set -Eeuo pipefail

SOFT_LIMIT="${SOFT_LIMIT:-65535}"
HARD_LIMIT="${HARD_LIMIT:-1048576}"

LIMITS_FILE="/etc/security/limits.d/99-nofile.conf"
SYSTEMD_SYSTEM_FILE="/etc/systemd/system.conf.d/99-nofile.conf"
SYSTEMD_USER_FILE="/etc/systemd/user.conf.d/99-nofile.conf"

log() {
    printf '\n\033[1;32m==> %s\033[0m\n' "$*"
}

warn() {
    printf '\033[1;33mWARNING: %s\033[0m\n' "$*" >&2
}

die() {
    printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2
    exit 1
}

backup_file() {
    local file="$1"

    if [[ -f "$file" ]]; then
        cp -a "$file" "${file}.bak.$(date +%Y%m%d-%H%M%S)"
    fi
}

[[ $EUID -eq 0 ]] || die "Hãy chạy script bằng sudo."

[[ "$SOFT_LIMIT" =~ ^[0-9]+$ ]] ||
    die "SOFT_LIMIT phải là số nguyên."

[[ "$HARD_LIMIT" =~ ^[0-9]+$ ]] ||
    die "HARD_LIMIT phải là số nguyên."

(( SOFT_LIMIT <= HARD_LIMIT )) ||
    die "SOFT_LIMIT không được lớn hơn HARD_LIMIT."

KERNEL_NR_OPEN="$(cat /proc/sys/fs/nr_open)"

(( HARD_LIMIT <= KERNEL_NR_OPEN )) ||
    die "HARD_LIMIT=${HARD_LIMIT} vượt fs.nr_open=${KERNEL_NR_OPEN}."

log "Cấu hình PAM limits"

mkdir -p /etc/security/limits.d
backup_file "$LIMITS_FILE"

cat > "$LIMITS_FILE" <<EOF
# Managed by update-ulimit.sh
# Soft limit mặc định cho các phiên đăng nhập.
*    soft    nofile    ${SOFT_LIMIT}
*    hard    nofile    ${HARD_LIMIT}
root soft    nofile    ${SOFT_LIMIT}
root hard    nofile    ${HARD_LIMIT}
EOF

chmod 0644 "$LIMITS_FILE"

log "Kiểm tra pam_limits.so"

for pam_file in \
    /etc/pam.d/common-session \
    /etc/pam.d/common-session-noninteractive
do
    if [[ -f "$pam_file" ]] &&
       ! grep -Eq '^[[:space:]]*session[[:space:]]+.*pam_limits\.so' "$pam_file"; then
        backup_file "$pam_file"
        printf '\nsession required pam_limits.so\n' >> "$pam_file"
        warn "Đã bổ sung pam_limits.so vào ${pam_file}"
    fi
done

log "Cấu hình mặc định cho systemd system services"

mkdir -p /etc/systemd/system.conf.d
backup_file "$SYSTEMD_SYSTEM_FILE"

cat > "$SYSTEMD_SYSTEM_FILE" <<EOF
# Managed by update-ulimit.sh
[Manager]
DefaultLimitNOFILE=${SOFT_LIMIT}:${HARD_LIMIT}
EOF

chmod 0644 "$SYSTEMD_SYSTEM_FILE"

log "Cấu hình mặc định cho systemd user services"

mkdir -p /etc/systemd/user.conf.d
backup_file "$SYSTEMD_USER_FILE"

cat > "$SYSTEMD_USER_FILE" <<EOF
# Managed by update-ulimit.sh
[Manager]
DefaultLimitNOFILE=${SOFT_LIMIT}:${HARD_LIMIT}
EOF

chmod 0644 "$SYSTEMD_USER_FILE"

log "Nạp lại cấu hình systemd"

systemctl daemon-reexec
systemctl daemon-reload

log "Kiểm tra các file cấu hình"

printf '\n--- %s ---\n' "$LIMITS_FILE"
cat "$LIMITS_FILE"

printf '\n--- %s ---\n' "$SYSTEMD_SYSTEM_FILE"
cat "$SYSTEMD_SYSTEM_FILE"

printf '\n--- %s ---\n' "$SYSTEMD_USER_FILE"
cat "$SYSTEMD_USER_FILE"

printf '\nKernel fs.nr_open: %s\n' "$KERNEL_NR_OPEN"

cat <<EOF

Hoàn tất cấu hình.

Giới hạn mới chưa áp dụng cho shell và tiến trình đang chạy.
Hãy reboot:

    sudo reboot

Sau khi đăng nhập lại, kiểm tra:

    ulimit -Sn
    ulimit -Hn
    cat /proc/\$\$/limits | grep -i "open files"

Kết quả dự kiến:

    soft nofile = ${SOFT_LIMIT}
    hard nofile = ${HARD_LIMIT}
EOF
