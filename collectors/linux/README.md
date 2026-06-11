# Humungousaur Linux Collectors

Linux collectors should use Rust or C for daemon work and kernel/desktop
integrations. Every collector must emit the shared event envelope.

Suggested collector crates:

- `file-events`: inotify watched-tree events.
- `file-access`: fanotify for privileged opt-in access semantics.
- `desktop-events`: DBus, AT-SPI, X11, and Wayland desktop signals.
- `devices`: udev, power, display, Bluetooth, and storage signals.
