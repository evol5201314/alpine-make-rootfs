#!/bin/sh -e
apk update
apk add alpine-make-rootfs openssh python3 py3-pip bash curl tzdata

alpine-make-rootfs \
  --branch "$BRANCH" \
  --packages "openrc openssh python3 py3-pip bash curl tzdata $EXTRA_PACKAGES" \
  --timezone "$TIMEZONE" \
  --fs-skel-dir /workspace/panel-skel \
  --script-chroot \
  /workspace/alpine-rootfs-$RUN_NUMBER.tar.gz - <<'INNER'
    # 设置 root 密码
    echo 'root:passwd' | chpasswd

    # 配置 SSH
    rc-update add sshd default
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

    # 安装 Python 包
    pip3 install --no-cache-dir --break-system-packages flask requests

    # 确保 startup.start 有执行权限（由 panel-skel 复制过来的）
    chmod +x /etc/local.d/startup.start 2>/dev/null || true

    # 添加 local 服务到开机自启
    rc-update add local default

    # 创建测试脚本（如果 panel-skel 里没放的话）
    mkdir -p /root/scripts
    if [ ! -f /root/scripts/test.py ]; then
      cat > /root/scripts/test.py <<'PYEOF'
#!/usr/bin/env python3
import datetime
print(f"✅ 测试脚本运行成功！时间: {datetime.datetime.now()}")
PYEOF
      chmod +x /root/scripts/test.py
    fi

    echo ""
    echo "=========================================="
    echo "✅ 构建完成！"
    echo "=========================================="
    echo "📌 固定 IP:    192.168.1.3"
    echo "📌 Flask 面板: http://192.168.1.3:5000"
    echo "📌 SSH 登录:   root@192.168.1.3 (密码: passwd)"
    echo "=========================================="
INNER
