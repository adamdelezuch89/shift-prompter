#!/bin/bash

# Stops the script if any command returns an error
set -e

# --- Configuration ---
APP_NAME="shift-prompter"
VERSION="1.0-2" # Increased version for the new build method
ARCH="all"
BUILD_DIR="${APP_NAME}_${VERSION}_${ARCH}"
LIB_DIR="$BUILD_DIR/usr/lib/$APP_NAME/lib" # Directory for bundled libraries

# --- Colors and messages ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}--- Starting the .deb package build process (with bundled libraries) ---${NC}"

# --- Step 1: Clean up previous builds ---
echo -e "${YELLOW}Step 1: Cleaning up previous artifacts...${NC}"
rm -rf "$BUILD_DIR" "${APP_NAME}"_*.deb venv_bundle

# --- Step 2: Create directory structure ---
echo -e "${YELLOW}Step 2: Creating the package directory structure...${NC}"
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$BUILD_DIR/usr/lib/$APP_NAME"
mkdir -p "$LIB_DIR"
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/usr/share/pixmaps"

# --- Step 3: Download Python dependencies locally ---
echo -e "${YELLOW}Step 3: Downloading Python dependencies (PyQt6, pynput)...${NC}"
# We create a temporary virtual environment to download packages
python3 -m venv venv_bundle
source venv_bundle/bin/activate
pip install -r requirements.txt
deactivate

# Copy the installed packages from site-packages into our library folder
# This makes the package self-contained
cp -r venv_bundle/lib/python*/site-packages/* "$LIB_DIR/"
rm -rf venv_bundle # Clean up the temporary venv

# --- Step 4: Copy application files ---
echo -e "${YELLOW}Step 4: Copying application files...${NC}"
cp main.py "$BUILD_DIR/usr/lib/$APP_NAME/"
cp icon.png "$BUILD_DIR/usr/share/pixmaps/$APP_NAME.png"

# --- Step 5: Create metadata and scripts ---
echo -e "${YELLOW}Step 5: Creating DEBIAN files, .desktop entry, and launcher script...${NC}"

# 5a: The 'control' file (now with fewer dependencies)
# IMPORTANT: Change the Maintainer field to your name and email.
cat <<'EOF' > "$BUILD_DIR/DEBIAN/control"
Package: shift-prompter
Version: 1.0-2
Architecture: all
Maintainer: Your Name <your.email@example.com>
Depends: python3, xclip, xdotool, wl-clipboard, wtype
Description: Local Prompt Manager for instant text pasting.
 Shift-Prompter is a lightweight Linux application that provides instant access
 to your predefined text snippets (prompts) via a global hotkey.
 This package bundles PyQt6 and pynput for compatibility with older systems.
EOF

# 5b: The 'postinst' script (runs after installation)
cat <<'EOF' > "$BUILD_DIR/DEBIAN/postinst"
#!/bin/bash
set -e
echo "--------------------------------------------------------"
echo "Shift-Prompter has been installed."
echo "For global hotkeys to work, add your user to the 'input' group:"
echo ""
echo "  sudo usermod -a -G input \$USER"
echo ""
echo "You must log out and log back in for this change to take effect."
echo "--------------------------------------------------------"
exit 0
EOF

# 5c: The launcher script (UPDATED to use bundled libs)
cat <<EOF > "$BUILD_DIR/usr/bin/$APP_NAME"
#!/bin/bash
APP_LIB_PATH="/usr/lib/$APP_NAME/lib"
export PYTHONPATH="\${APP_LIB_PATH}:\${PYTHONPATH}"
exec python3 /usr/lib/$APP_NAME/main.py "\$@"
EOF

# 5d: The .desktop file
cat <<EOF > "$BUILD_DIR/usr/share/applications/$APP_NAME.desktop"
[Desktop Entry]
Version=1.0
Name=Shift-Prompter
Comment=Local Prompt Manager for instant text pasting
Exec=/usr/bin/$APP_NAME
Icon=/usr/share/pixmaps/$APP_NAME.png
Terminal=false
Type=Application
Categories=Utility;
StartupNotify=false
EOF

# --- Step 6: Set correct permissions ---
echo -e "${YELLOW}Step 6: Setting correct file permissions...${NC}"
sudo chown -R root:root "$BUILD_DIR"
sudo chmod 755 "$BUILD_DIR/DEBIAN/postinst"
sudo chmod 755 "$BUILD_DIR/usr/bin/$APP_NAME"

# --- Step 7: Build the .deb package ---
echo -e "${YELLOW}Step 7: Building the final .deb package...${NC}"
dpkg-deb --build "$BUILD_DIR"

# --- Step 8: Clean up ---
echo -e "${YELLOW}Step 8: Cleaning up temporary files...${NC}"
sudo rm -r "$BUILD_DIR"

FINAL_DEB="${APP_NAME}_${VERSION}_${ARCH}.deb"
echo -e "${GREEN}--- SUCCESS! ---${NC}"
echo -e "Created package: ${GREEN}$FINAL_DEB${NC}"
echo -e "You can now install it using: ${YELLOW}sudo apt install ./$FINAL_DEB${NC}"