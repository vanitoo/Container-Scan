# gui/themes.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from pdf_ocr_app.utils.logger import logger


def _disable_native_treeview_selection(style: ttk.Style) -> None:
    """Let Treeview row tags control selected-row colors.

    ttk themes (including sv_ttk) normally paint the selected state with their
    own blue background. That state map has higher priority than item tags, so
    status colors such as exact_match_selected are hidden. Removing the native
    selected foreground/background maps keeps the real Treeview selection for
    keyboard/focus logic while the row tags remain visually visible.
    """
    style.map("Treeview", background=[], foreground=[])


def apply_minimal_theme(root, theme="light"):
    """Применение минималистичной темы"""
    style = ttk.Style(root)

    try:
        import sv_ttk

        sv_ttk.set_theme(theme)
        logger.debug(f"sv_ttk применена: {theme}")
        use_sv = True
        _disable_native_treeview_selection(style)
    except Exception as e:
        use_sv = False
        style.theme_use("clam")
        logger.debug(f"sv_ttk ошибка: {e}")

        if theme == "dark":
            BG = "#1F2937"
            FG = "#E5E7EB"
            ACCENT = "#3B82F6"
            MUTED = "#9CA3AF"
        else:
            BG = "#F7F7F9"
            FG = "#111827"
            ACCENT = "#2563EB"
            MUTED = "#6B7280"

        style.configure(".", background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("TButton", padding=8, relief="flat")
        style.map("TButton", background=[("active", "#E5E7EB")], relief=[("pressed", "sunken")])
        style.configure("Toolbar.TFrame", background=BG)
        style.configure("ToolSep.TFrame", background="#E5E7EB")
        style.configure("TEntry", padding=6)
        style.configure("TCombobox", padding=6)
        style.configure("Treeview", borderwidth=0, rowheight=28, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI Semibold", 10), foreground=MUTED)
        _disable_native_treeview_selection(style)

    def style_treeview_stripes(tree):
        try:
            tree.tag_configure("oddrow", background="#F3F4F6")
            for i, iid in enumerate(tree.get_children("")):
                if i % 2 == 1:
                    tree.item(iid, tags=("oddrow",))
        except Exception as e:
            logger.debug(f"Не удалось установить тег oddrow: {e}")

    def build_toolbar(parent, *widgets):
        bar = ttk.Frame(parent, style="Toolbar.TFrame")
        bar.pack(side="top", fill="x")
        for w in widgets:
            w.pack(in_=bar, side="left", padx=6, pady=8)
        sep = ttk.Frame(parent, style="ToolSep.TFrame", height=1)
        sep.pack(side="top", fill="x")
        return bar

    root._style_helpers = {
        "style_treeview_stripes": style_treeview_stripes,
        "build_toolbar": build_toolbar,
        "sv_ttk": use_sv,
    }


def toggle_theme(root):
    """Переключение темы"""
    helpers = getattr(root, "_style_helpers", {})
    style = ttk.Style(root)

    if helpers.get("sv_ttk"):
        try:
            import sv_ttk

            sv_ttk.toggle_theme()
            # Переключение sv_ttk восстанавливает стандартную синюю подсветку,
            # поэтому сразу снова отдаём фон/текст выбранной строки её тегам.
            _disable_native_treeview_selection(style)
            return
        except Exception as e:
            logger.debug(f"Ошибка при переключении темы: {e}")

    current = getattr(root, "_theme_mode", "light")
    if current == "light":
        # Тёмная тема
        BG = "#111827"
        FG = "#E5E7EB"
        MUTED = "#9CA3AF"
        TB_BG = "#0F172A"
        SEP = "#1F2937"
        style.configure(".", background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("TButton", padding=8)
        style.configure("Toolbar.TFrame", background=TB_BG)
        style.configure("ToolSep.TFrame", background=SEP)
        style.configure("Treeview", background=BG, fieldbackground=BG, foreground=FG, rowheight=28)
        style.configure("Treeview.Heading", foreground=MUTED)
        _disable_native_treeview_selection(style)
        root._theme_mode = "dark"
    else:
        # Светлая тема
        BG = "#F7F7F9"
        FG = "#111827"
        MUTED = "#6B7280"
        TB_BG = BG
        SEP = "#E5E7EB"
        style.configure(".", background=BG, foreground=FG, font=("Segoe UI", 10))
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("TButton", padding=8)
        style.configure("Toolbar.TFrame", background=TB_BG)
        style.configure("ToolSep.TFrame", background=SEP)
        style.configure("Treeview", background=BG, fieldbackground=BG, foreground=FG, rowheight=28)
        style.configure("Treeview.Heading", foreground=MUTED)
        _disable_native_treeview_selection(style)
        root._theme_mode = "light"
