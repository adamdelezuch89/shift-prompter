# Shift-Prompter (Local Prompt Manager)

Shift-Prompter is a lightweight Linux application that provides instant access to your predefined text snippets (prompts). The entire application runs locally, with no need to connect to external services.

The application is activated by a global hotkey (a quick double-press of the `Shift` key), which opens a small window with a list of your snippets. Selecting a snippet instantly pastes it at your current cursor position.

## Features

- **Instant Access**: Use the `Shift` + `Shift` shortcut anywhere in the system to open the prompt list window.
- **Prompt Management**: A simple interface to add, edit, and delete your own text snippets.
- **Local Database**: All your prompts are stored locally in the `~/.config/Shift-Prompter/prompts.json` file.
- **Contextual Pasting**: The selected text is automatically pasted into the active window at the cursor's location.
- **System Integration**: Installs like a native application with a menu entry.

## System Requirements

- **Debian-based Linux Operating System** (e.g., Ubuntu, Mint, Pop!_OS)
- All other dependencies (like Python, PyQt6, and command-line tools) are automatically installed with the package.

## Installation (for Users)

1.  Download the latest `.deb` file from the [Releases](https://github.com/username/shift-prompter/releases) section.
2.  Open a terminal in the directory where you downloaded the file.
3.  Run the following command to install the application and all its dependencies:
    ```bash
    sudo apt install ./shift-prompter_*.deb
    ```

After installation, "Shift-Prompter" will be available in your application menu.

## Building the `.deb` Package (for Developers)

### Prerequisites
1.  Clone the repository and navigate into its directory.
2.  Ensure you have the `dpkg-deb` tool, which is standard on most Debian-based systems.

### Build Process
The process is fully automated. Just run the following commands in the project's root directory:

```bash
# First, make the script executable
chmod +x build.sh

# Then, run it. It will ask for sudo password to set file permissions.
./build.sh
```
The script will create the final `.deb` package in the project directory.

## Usage

1.  Launch "Shift-Prompter" from your application menu or by running `shift-prompter` in a terminal. The application will run in the background.
2.  Anywhere you can input text, **quickly double-press the left or right `Shift` key** to open the prompt window.
3.  Select a prompt from the list (by double-clicking it or pressing `Enter`) to paste it. You can also use the buttons to manage the list.
4.  To close the window without selecting anything, you can:
    - **Double-press the `Shift` key again.**
    - **Press the `Escape` key.**
    - **Click outside the window.**

## Permissions for Global Hotkey

For the global hotkey to work, your user account must have permission to read input devices. This is a one-time setup.

1.  Add your user to the `input` group by running this command:
    ```bash
    sudo usermod -a -G input $USER
    ```
2.  **You must log out and back in** for this change to take effect.

## Adding to Autostart

To have Shift-Prompter launch automatically every time you log in, add it to your desktop environment's startup applications.

**For Ubuntu (GNOME) and similar environments:**

1.  Search for and open the "**Startup Applications**" utility.
2.  Click the "**Add**" button.
3.  Fill in the fields:
    - **Name:** `Shift-Prompter`
    - **Command:** `/usr/bin/shift-prompter`
    - **Comment:** `Starts the local prompt manager`
4.  Click "**Add**" to save.

For other desktop environments (like KDE Plasma, XFCE), find the "Autostart" or "Startup and Shutdown" section in your System Settings and add a new application entry with the command `/usr/bin/shift-prompter`.

## License

[MIT](LICENSE)