TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "type_text",
            "description": (
                "Type text into the currently focused app on screen — a terminal, VS Code, a text field, etc. "
                "ONLY use this when you are actively controlling the computer (e.g. running Claude Code, "
                "typing a shell command, filling a form). "
                "NEVER use this to reply to the user — speak to the user with plain text responses instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to type. Can be a shell command, a Claude Code prompt, or any other input."
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": (
                "Press a key or keyboard shortcut on the computer. "
                "ONLY use when actively controlling an app on screen — opening a terminal, "
                "submitting a command, interrupting a process, etc. "
                "NEVER use this to reply to the user. "
                "Examples: 'return' (submit), 'ctrl+backtick' (open VS Code terminal), "
                "'ctrl+c' (interrupt), 'ctrl+l' (clear terminal), 'up' (command history)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {
                        "type": "string",
                        "description": (
                            "Key or shortcut to press. Examples: "
                            "'return' (submit/Enter), "
                            "'escape' (cancel), "
                            "'ctrl+backtick' (open VS Code terminal), "
                            "'ctrl+c' (interrupt process), "
                            "'ctrl+l' (clear terminal), "
                            "'up' (previous command in history), "
                            "'tab' (autocomplete), "
                            "'cmd+k' (clear terminal on macOS)."
                        )
                    }
                },
                "required": ["keys"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "wait_seconds",
            "description": (
                "Wait for a number of seconds before the next action. "
                "Use after opening an app, running a command, or any time you need to let "
                "something load or process before reading the screen again. "
                "Typical values: 1-3s for UI actions, 5-10s for app launches, "
                "15-30s for long-running commands like Claude Code."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "integer",
                        "description": "Number of seconds to wait (1–60)."
                    }
                },
                "required": ["seconds"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open a desktop application by name. Use for apps like VS Code, Chrome, Figma, Illustrator, Spotify, Terminal, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "App name: 'vscode', 'chrome', 'figma', 'illustrator', 'spotify', 'terminal', 'firefox', 'notion', 'slack', etc."
                    }
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "close_app",
            "description": "Close / quit a running desktop application.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "App name to close."}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_project",
            "description": "Open a named coding project folder in VS Code. Only use when the user explicitly names a project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Project folder name."}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_terminal",
            "description": "Run a shell command in the terminal and return its output. Do NOT use for opening websites or applications.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to execute."}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_design_project",
            "description": "Create a new design project folder with standard subfolders (assets, exports, source, references).",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Name of the new design project."}
                },
                "required": ["name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_design_folder",
            "description": "Open the main Design folder in Finder.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_exports_to_desktop",
            "description": "Copy all export files from a design project's exports folder to the Desktop.",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "Name of the design project."}
                },
                "required": ["project_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search Google for a query and open the results in the browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query string."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Open a specific URL in the browser. Optionally specify which browser to use.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "Full URL or shortcut like 'github', 'figma', 'mdn'."
                    },
                    "browser": {
                        "type": "string",
                        "description": "Optional: 'chrome', 'firefox', 'safari', 'edge', 'brave'."
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_youtube",
            "description": "Search YouTube and automatically play the first video result. This tool opens Chrome and YouTube by itself — do NOT call open_app or open_url before it. Use for any music, video, or gaming content unless the user says Spotify.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "YouTube search query."}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_spotify",
            "description": "Open Spotify and play a track, playlist, or album by name or URI. Use when user says 'Spotify' or names a saved playlist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Playlist/track name, Spotify URI, or Spotify URL."
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_screen",
            "description": "Take a screenshot and use vision AI to answer a question about what is currently on screen. Use when the user asks about screen content without specifying it, or when you need to observe results after opening an app or URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Question to answer about the current screen contents."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "take_screenshot",
            "description": "Capture a screenshot and save it to the Desktop.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_clipboard",
            "description": "Read and return the current contents of the clipboard.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "control_volume",
            "description": "Control the system volume.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["up", "down", "mute"],
                        "description": "Volume action: 'up', 'down', or 'mute'."
                    }
                },
                "required": ["action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "start_focus_timer",
            "description": "Start a focus / Pomodoro timer. Aria will notify you when time is up.",
            "parameters": {
                "type": "object",
                "properties": {
                    "minutes": {
                        "type": "integer",
                        "description": "Timer duration in minutes."
                    }
                },
                "required": ["minutes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remind_me",
            "description": "Set a voice reminder to trigger after a delay.",
            "parameters": {
                "type": "object",
                "properties": {
                    "minutes": {
                        "type": "integer",
                        "description": "Delay in minutes before the reminder fires."
                    },
                    "message": {
                        "type": "string",
                        "description": "The reminder message to speak aloud."
                    }
                },
                "required": ["minutes", "message"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "switch_voice",
            "description": "Switch Aria's text-to-speech voice to a different language preset.",
            "parameters": {
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "description": "Language preset: 'arabic', 'english', 'japanese', 'default'."
                    }
                },
                "required": ["language"]
            }
        }
    },
]
