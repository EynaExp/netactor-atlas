FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Core system deps + nmap + masscan
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    nodejs \
    npm \
    jq \
    unzip \
    ca-certificates \
    nmap \
    masscan \
    xvfb \
    libasound2t64 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxss1 \
    && rm -rf /var/lib/apt/lists/*

# GenOffice CLI - AI Office suite for document generation (Word/PDF from Markdown)
RUN DEB_URL=$(curl -sL "https://api.github.com/repos/genspark-ai/genoffice/releases/latest" | \
      python3 -c "import sys,json; assets=json.load(sys.stdin).get('assets',[]); urls=[x['browser_download_url'] for x in assets if x['name'].endswith('.deb')]; print(urls[0] if urls else '')") && \
    [ -n "$DEB_URL" ] && \
    curl -sL "$DEB_URL" -o /tmp/genoffice.deb && \
    apt-get update && apt-get install -y /tmp/genoffice.deb && \
    rm /tmp/genoffice.deb && \
    rm -rf /var/lib/apt/lists/*

# NetExec (nxc) prebuilt standalone binary from GitHub releases
RUN curl -sL https://github.com/Pennyw0rth/NetExec/releases/download/v1.5.0/nxc-ubuntu-latest.zip -o /tmp/nxc.zip && \
    unzip -o /tmp/nxc.zip -d /usr/local/bin/ && \
    rm /tmp/nxc.zip && \
    chmod +x /usr/local/bin/nxc* 2>/dev/null || true

# searchsploit (exploitdb) - moved to GitLab, use archive tarball
RUN curl -sL https://gitlab.com/exploit-database/exploitdb/-/archive/main/exploitdb-main.tar.gz -o /tmp/expdb.tar.gz && \
    tar -xzf /tmp/expdb.tar.gz -C /opt/ && \
    mv /opt/exploitdb-main /opt/exploitdb && \
    rm /tmp/expdb.tar.gz && \
    ln -sf /opt/exploitdb/searchsploit /usr/local/bin/searchsploit

# ADscan (Active Directory pentesting) with all runtime dependencies
RUN git clone --depth 1 https://github.com/ADScanPro/adscan.git /opt/adscan && \
    pip install --break-system-packages --no-cache-dir /opt/adscan && \
    pip install --break-system-packages --no-cache-dir \
        psutil \
        prompt_toolkit \
        pygments \
        questionary \
        dnspython \
        impacket \
        pycryptodome \
        pypsrp \
        pypykatz \
        scapy \
        python-docx \
        openpyxl \
        pdfplumber \
        python-magic \
        netifaces \
        pydantic \
        textual \
        redis \
        rustworkx \
        pyyaml \
    && ln -sf /opt/adscan/adscan.py /usr/local/bin/adscan

# adPEAS (winPEAS for Active Directory) - runs BloodHound + Certipy + AD enumeration
# setup.py in repo has a typo (missing newline in install_requires), patch it before install
RUN git clone --depth 1 https://github.com/ajm4n/adPEAS /opt/adPEAS && \
    python3 -c "import re,pathlib; p=pathlib.Path('/opt/adPEAS/setup.py'); s=p.read_text(); s=s.replace(\"'termcolor==2.5.0'\n          'beautifulsoup4'\", \"'termcolor==2.5.0',\n          'beautifulsoup4'\"); p.write_text(s)" && \
    pip install --break-system-packages --no-cache-dir --no-deps /opt/adPEAS && \
    pip install --break-system-packages --no-cache-dir \
        certipy-ad \
        impacket \
        ldap3==2.9.1 \
        regex \
        termcolor \
        beautifulsoup4 \
        bloodhound-python && \
    pip install --break-system-packages --no-cache-dir "certi @ git+https://github.com/zer1t0/certi@main"

# Nuclei - template-based vulnerability scanner (web, network/tcp, ssl, dns)
RUN curl -sL https://github.com/projectdiscovery/nuclei/releases/download/v3.3.9/nuclei_3.3.9_linux_amd64.zip -o /tmp/nuclei.zip && \
    cd /tmp && unzip -o nuclei.zip nuclei && mv nuclei /usr/local/bin/ && rm -f nuclei.zip && \
    nuclei -update-templates

# Create workspace
RUN mkdir -p /workspace
WORKDIR /workspace

# Copy MCP server
COPY mcp-server/ /app/mcp-server/
RUN cd /app/mcp-server && npm install

EXPOSE 3001

CMD ["node", "/app/mcp-server/index.js"]
