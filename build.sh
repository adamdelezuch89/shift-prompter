#!/bin/bash

# Stops the script if any command returns an error
set -e

# --- Configuration ---
APP_NAME="shift-prompter"
VERSION="1.0-3" # Increased version for new improvements
ARCH=$(dpkg --print-architecture) # Use system architecture for better accuracy
BUILD_DIR="${APP_NAME}_${VERSION}_${ARCH}"
LIB_DIR="$BUILD_DIR/usr/lib/$APP_NAME/lib" # Directory for bundled libraries

# --- Colors and messages ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}--- Starting the .deb package build process (v3) ---${NC}"

# --- Step 1: Clean up previous builds ---
echo -e "${YELLOW}Step 1: Cleaning up previous artifacts...${NC}"
rm -rf "$BUILD_DIR" "${APP_NAME}"_*.deb

# --- Step 2: Create directory structure ---
echo -e "${YELLOW}Step 2: Creating the package directory structure...${NC}"
mkdir -p "$BUILD_DIR/DEBIAN"
mkdir -p "$BUILD_DIR/usr/bin"
mkdir -p "$LIB_DIR" # This also creates /usr/lib/$APP_NAME
mkdir -p "$BUILD_DIR/usr/share/applications"
mkdir -p "$BUILD_DIR/usr/share/pixmaps"

# --- Step 3: Install Python dependencies directly into the target directory ---
echo -e "${YELLOW}Step 3: Installing Python dependencies into target directory...${NC}"
pip install --target="$LIB_DIR" -r requirements.txt

# --- Step 4: Copy application files ---
echo -e "${YELLOW}Step 4: Copying application files...${NC}"
cp main.py "$BUILD_DIR/usr/lib/$APP_NAME/"
cp icon.png "$BUILD_DIR/usr/share/pixmaps/$APP_NAME.png"

# --- Step 5: Create metadata and scripts ---
echo -e "${YELLOW}Step 5: Creating DEBIAN files, .desktop entry, and launcher script...${NC}"

# 5a: The 'control' file
# IMPORTANT: Change the Maintainer field to your name and email.
# NOTE: Changed Architecture to be dynamic based on the build system.
cat <<EOF > "$BUILD_DIR/DEBIAN/control"
Package: ${APP_NAME}
Version: ${VERSION}
Architecture: ${ARCH}
Maintainer: Your Name <your.email@example.com>
Depends: python3, xclip, xdotool, wl-clipboard, wtype
Description: Local Prompt Manager for instant text pasting.
 Shift-Prompter is a lightweight Linux application that provides instant access
 to your predefined text snippets (prompts) via a global hotkey.
 This package bundles PyQt6 and pynput for easier installation.
EOF

# 5b: The 'postinst' script
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

# 5c: The launcher script
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

# --- Step 6: Set correct executable permissions ---
echo -e "${YELLOW}Step 6: Setting executable permissions...${NC}"
chmod 755 "$BUILD_DIR/DEBIAN/postinst"
chmod 755 "$BUILD_DIR/usr/bin/$APP_NAME"

# --- Step 6.5: Clean up bytecode files to reduce package size ---
echo -e "${YELLOW}Step 6.5: Cleaning up bytecode files...${NC}"
find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -r {} +
find "$BUILD_DIR" -type f -name "*.pyc" -delete

# --- Step 7: Build the .deb package using fakeroot ---
echo -e "${YELLOW}Step 7: Building the final .deb package...${NC}"
fakeroot dpkg-deb --build "$BUILD_DIR"

# --- Step 8: Clean up ---
echo -e "${YELLOW}Step 8: Cleaning up temporary build directory...${NC}"
rm -r "$BUILD_DIR" # No sudo needed

FINAL_DEB="${APP_NAME}_${VERSION}_${ARCH}.deb"
echo -e "${GREEN}--- SUCCESS! ---${NC}"
echo -e "Created package: ${GREEN}$FINAL_DEB${NC}"
echo -e "You can now install it using: ${YELLOW}sudo apt install ./$FINAL_DEB${NC}"