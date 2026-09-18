#!/bin/bash
# Downloads all vendored files needed for offline container builds.
# Run this after cloning the repo, BEFORE ./deploy/netactor.sh build
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$DIR/vendor" "$DIR/wheels" "$DIR/bin"

echo "[1/5] nxc binary..."
if [ ! -f "$DIR/bin/nxc.zip" ]; then
    curl -sL -o "$DIR/bin/nxc.zip" \
        https://github.com/Pennyw0rth/NetExec/releases/download/v1.5.0/nxc-ubuntu-latest.zip
fi

echo "[2/5] nuclei binary..."
if [ ! -f "$DIR/bin/nuclei" ]; then
    curl -sL -o /tmp/nuclei.zip https://github.com/projectdiscovery/nuclei/releases/download/v3.3.9/nuclei_3.3.9_linux_amd64.zip
    unzip -o /tmp/nuclei.zip -d /tmp/nuclei-bin
    mv /tmp/nuclei-bin/nuclei "$DIR/bin/nuclei"
    chmod +x "$DIR/bin/nuclei"
    rm -rf /tmp/nuclei.zip /tmp/nuclei-bin
fi

echo "[3/5] exploitdb..."
if [ ! -d "$DIR/vendor/exploitdb" ]; then
    curl -sL -o /tmp/expdb.tar.gz https://gitlab.com/exploit-database/exploitdb/-/archive/main/exploitdb-main.tar.gz
    tar -xzf /tmp/expdb.tar.gz -C /tmp
    mv /tmp/exploitdb-main "$DIR/vendor/exploitdb"
    rm /tmp/expdb.tar.gz
fi

echo "[4/5] adscan + adPEAS..."
[ -d "$DIR/vendor/adscan" ] || git clone --depth 1 https://github.com/ADScanPro/adscan.git "$DIR/vendor/adscan"
[ -d "$DIR/vendor/adPEAS" ] || git clone --depth 1 https://github.com/ajm4n/adPEAS "$DIR/vendor/adPEAS"

echo "[5/5] pip wheels..."
if [ ! -f "$DIR/wheels/impacket"*.whl ] 2>/dev/null; then
    pip3 download --dest "$DIR/wheels" --no-cache-dir \
        psutil prompt_toolkit pygments questionary dnspython \
        impacket pycryptodome pypsrp pypykatz scapy \
        python-docx openpyxl pdfplumber python-magic netifaces \
        pydantic textual redis rustworkx pyyaml \
        certipy-ad ldap3==2.9.1 regex termcolor beautifulsoup4 \
        bloodhound-python "certi @ git+https://github.com/zer1t0/certi@main" -q
fi

echo ""
echo "Done. Vendor folder:"
du -sh "$DIR/vendor" "$DIR/wheels" "$DIR/bin" 2>/dev/null