# Related projects (surveyed 2026-10-24)

| Project | What | Take from it |
|---|---|---|
| [WeClone](https://github.com/xming521/WeClone) (AGPL-3.0) | LoRA fine-tune (Qwen2.5-VL-7B via LLaMA Factory) on WeChat/Telegram chats; PII filter; separate WeClone-audio voice clone; bots on Telegram/Discord/Slack. WhatsApp "coming soon". 16GB+ GPU. | Preprocessing/PII ideas, fine-tune recipe for M8. **Don't copy code** (AGPL). |
| [chat-clone-ai-local](https://github.com/ArchBase/chat-clone-ai-local) | Persona from WhatsApp .txt for a chosen participant, local via Ollama. Text only. | WhatsApp parsing edge cases. |
| [doppelganger-gpt](https://github.com/sanggubot/doppelganger-gpt) | KakaoTalk + OpenAI + vector search (LangChain), no training. | Same retrieval-of-real-replies approach as D-002. |
| personal-chat-slm, chat_nlp | Toy models trained on WhatsApp exports. | Not useful beyond curiosity. |
| TwinChat (Waken.ai), Dolly AI | Commercial clones from WhatsApp chats. | Product reference. |
| HereAfter AI, StoryFile, Delphi.ai, Project December | Memorial / creator clones (interviews, voice). | Consent & UX framing. |

Gap none of them fill: expressive voice driven by the person's own emoji/emotion habits + chat-specific privacy guardrail.
