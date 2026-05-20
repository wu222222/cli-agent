FROM kalilinux/kali-rolling:latest

# 预装常用渗透测试工具（不含 metasploit，按需再装）
# 1. 先用 http 换源，规避 SSL 证书未更新导致的握手失败
RUN sed -i 's@http://http.kali.org/kali@http://mirrors.aliyun.com/kali@g' /etc/apt/sources.list.d/kali.sources && \
    apt-get update && \
    # 2. 顺手把证书库和基础工具装上，后续系统就支持 https 了
    apt-get install -y --no-install-recommends ca-certificates && \
    apt-get install -y --no-install-recommends \
    # 网络基础（ping / ip / ifconfig / ss / nslookup）
    iputils-ping \
    iproute2 \
    net-tools \
    dnsutils \
    netcat-openbsd \
    whois \
    # 网络扫描
    nmap \
    # Web 漏洞
    nikto \
    sqlmap \
    gobuster \
    dirb \
    wfuzz \
    # 密码攻击
    hydra \
    john \
    # 漏洞搜索
    exploitdb \
    # SMB / 域渗透
    enum4linux \
    smbclient \
    # 基础工具
    curl wget git \
    python3 python3-pip \
    wordlists \
    # 清理缓存减小镜像体积
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 工作目录，挂载到宿主机 ./workspace 以便保存结果
WORKDIR /workspace

CMD ["/bin/bash"]
