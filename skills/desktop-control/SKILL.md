---
name: desktop-control
description: Parent skill for local app control, accessibility, windows, files, clipboard, screenshots, OCR, UI automation, and local service troubleshooting.
---

# Desktop Control

## Purpose

Use this parent skill when a task requires observing or controlling local desktop state, apps, files, windows, clipboard, screenshots, OCR, or local services.

## Hierarchy Reading Rules

1. Prefer semantic app, file, or accessibility tools before coordinate-based control.
2. Load the specific child skill for the surface: UI, window, clipboard, file navigation, screenshot OCR, or service troubleshooting.
3. Observe before acting, then verify after every state-changing action.
4. Keep destructive, account-changing, and irreversible actions approval-gated.

## Tool Map

- `accessibility-assistance`
- `app-launch-and-window-management`
- `clipboard-operations`
- `desktop-ui-control`
- `keyboard-mouse-screen-control`
- `local-app-troubleshooting`
- `local-file-navigation`
- `local-service-monitoring`
- `screenshot-ocr-review`

## Child Skill Guide

- Use desktop UI, accessibility, keyboard/mouse/screen, and screenshot OCR skills for visible app interaction.
- Use app launch/window management for focus, sizing, launching, and window state.
- Use clipboard and local file navigation for data transfer and filesystem workflows.
- Use local app troubleshooting and service monitoring for running processes, logs, ports, and health checks.

## Verification

- Confirm observed UI state before and after interaction.
- Report when a target is not visible, ambiguous, stale, or blocked by permissions.
