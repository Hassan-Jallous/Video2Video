# Video2Video 🎬

AI-Powered TikTok Video Clone Platform - Transform any TikTok video into AI-generated recreations using Google Veo 3.1 & Sora 2.

## 🎯 Features

- **Multi-Provider Support**: Choose between Kie.ai (high quality) or defapi.org (budget)
- **Multi-Model Support**: Veo 3.1 (Fast/Quality) and Sora 2/Pro
- **Dual Strategy**:
  - Seamless Video (Extend Feature) - Single continuous video
  - Separate Segments (Default) - Multiple clips for editing
- **Product-Focused**: Upload product images and names for precise AI generation
- **Multiple Variants**: Generate same video N times for A/B testing
- **AI Analysis**: Frame-by-frame product video analysis with Gemini 2.5 Pro
- **Smart Segmentation**: Intelligent scene detection with PySceneDetect
- **Video Library**: Persistent storage with batch download support

## 🏗️ Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **yt-dlp** - TikTok video downloader
- **PySceneDetect** - Scene detection
- **Google Gemini API** - Product video analysis
- **Kie.ai API** - High quality video generation
- **defapi.org API** - Budget video generation
- **Celery + Redis** - Background task processing

### Frontend
- **Next.js 14** - React framework with TypeScript
- **TailwindCSS** - Styling
- **Vercel** - Deployment

## 📋 Prerequisites

- Python 3.10+
- Node.js 18+
- Redis (for background tasks)
- Google Gemini API Key
- **Video Generation Provider** (choose one or both):
  - Kie.ai API Key (High Quality, Production)
  - defapi.org API Key (Budget, Testing)

## 🚀 Quick Start

Coming soon...

## 💰 Cost Estimates (30s Video, Single Variant)

### Strategy B (Separate Segments) - Default
**Kie.ai (High Quality)**:
- **Sora 2**: $0.45 (3x 10s clips)
- **Veo 3.1 Fast**: $1.60 (4x 8s clips)
- **Veo 3.1 Quality**: $8.00 (4x 8s clips)

**defapi.org (Budget/Testing)**:
- **Sora 2**: $0.30 (3 videos) 🔥 Cheapest!
- **Veo 3.1**: $0.40 (4 videos) 🔥 Ultra Budget!

### Strategy A (Seamless)
**Kie.ai**:
- **Sora 2**: ~$2.15 (base + 2x extend)
- **Veo 3.1 Fast**: ~$4.40 (base + 3x extend)
- **Veo 3.1 Quality**: ~$14.00 (base + 3x extend)

**defapi.org**:
- **Sora 2**: ~$0.30 (3 videos) 🔥 75% cheaper!
- **Veo 3.1**: ~$0.40 (4 videos) 🔥 90% cheaper!

## 📚 Documentation

- [Implementation Plan](./.claude/plans/glistening-marinating-quill.md)
- [API Documentation](./docs/api.md) - Coming soon
- [Deployment Guide](./docs/deployment.md) - Coming soon

## 🎬 How It Works

1. **Input**: User provides TikTok video URL
2. **Download**: Video downloaded using yt-dlp (no watermark)
3. **Analysis**: Gemini 2.5 Pro analyzes frame-by-frame
4. **Segmentation**: PySceneDetect splits into optimal segments
5. **Prompt Generation**: Creates detailed cinematic prompts
6. **Video Generation**: AI model creates videos based on prompts
7. **Output**: Download generated videos (ZIP or individual)

## 🔗 Resources

- [Google Veo 3.1 Docs](https://cloud.google.com/vertex-ai/generative-ai/docs/video/video-gen-prompt-guide)
- [Gemini Video API](https://ai.google.dev/gemini-api/docs/video-understanding)
- [Kie.ai API](https://kie.ai/market)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [PySceneDetect](https://github.com/Breakthrough/PySceneDetect)

## 📄 License

MIT

## 🤝 Contributing

Contributions welcome! Please read our contributing guidelines first.

---

**Status**: 🚧 MVP Development (Week 1 of 3)

Built with ❤️ using Claude Code
