# Kitchen Chat 🍳💬

A modern, real-time chat application for kitchen discussions, built with Python (Flask/Vercel) backend and vanilla JavaScript frontend.

## 🌟 Features

### ✨ User Interface
- **Modern Design**: Gradient backgrounds, glassmorphism effects, and smooth animations
- **Responsive Layout**: Works perfectly on desktop, tablet, and mobile devices
- **Dark Mode Ready**: Preparation for future dark mode implementation
- **Real-time Updates**: Automatic refresh of messages and topics

### 💬 Chat Functionality
- **Create Topics**: Start new conversations with custom titles
- **Real-time Messages**: Instant messaging with immediate feedback
- **User Names**: Personalization with saved user preferences
- **Search Feature**: Quickly find specific topics
- **Auto-refresh**: Messages automatically refresh every 30 seconds

### 🔧 Technical Features
- **Offline Detection**: Reports internet connection status
- **Loading States**: Clear feedback during API calls
- **Error Handling**: User-friendly error messages
- **PWA Ready**: Service Worker support (expandable)
- **Accessibility**: Keyboard navigation and screen reader support

## 🚀 Live Demo

**Frontend URL**: [kitchen-chat.vercel.app](https://kitchen-chat.vercel.app)

## 📁 Project Structure

```
Kitchen-chat/
├── index.html          # Main HTML file
├── styles.css          # Modern CSS styling
├── script.js           # Frontend JavaScript logic
├── vercel.json         # Vercel configuration
├── requirements.txt    # Python dependencies
├── api/
│   ├── posts.py       # API for messages
│   └── subjects.py    # API for topics
└── README.md          # This documentation
```

## 🛠 Technology Stack

### Frontend
- **HTML5**: Semantic markup with modern structure
- **CSS3**: 
  - Custom CSS properties (variables)
  - Flexbox and Grid layouts
  - CSS animations and transitions
  - Responsive design with media queries
  - Glassmorphism effects
- **JavaScript (ES6+)**:
  - Modern class-based architecture
  - Async/await for API calls
  - LocalStorage for user preferences
  - Event delegation for performance

### Backend
- **Python**: Serverless functions on Vercel
- **Firebase Firestore**: NoSQL database for messages and topics
- **Firebase Admin SDK**: Secure database access

### Deployment
- **Vercel**: Hosting for frontend and API
- **Firebase**: Cloud database service

## 🎨 Design System

### Color Palette
```css
/* Primary colors */
--primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
--primary-blue: #667eea;
--primary-purple: #764ba2;

/* Gray scale */
--gray-900: #2d3748;
--gray-600: #718096;
--gray-400: #a0aec0;
--gray-100: #f7fafc;

/* Status colors */
--success: #38a169;
--error: #e53e3e;
--warning: #d69e2e;
```

### Typography
- **Font**: Inter (fallback to system fonts)
- **Weights**: 400 (regular), 500 (medium), 600 (semibold), 700 (bold)
- **Responsive font sizes**: Scalable for all screen sizes

### Spacing System
- **Base unit**: 0.25rem (4px)
- **Scale**: 0.5rem, 0.75rem, 1rem, 1.5rem, 2rem, etc.
- **Consistent margins and padding** throughout application

## 📱 Responsive Design

### Desktop (1200px+)
- **Sidebar**: 320px fixed width for topics
- **Chat Area**: Flexible width for messages
- **Two-column layout**: Optimal for large screens

### Tablet (768px - 1199px)
- **Sidebar**: Full width, 40vh height
- **Chat Area**: Full width, 60vh height
- **Stacked layout**: Vertical organization

### Mobile (< 768px)
- **Single column**: All elements at full width
- **Touch-friendly**: Larger buttons and input fields
- **Optimized spacing**: Adjusted margins and padding

## ⚡ Performance Optimizations

### Frontend
- **Lazy Loading**: Messages loaded only when needed
- **Event Delegation**: Efficient event handling
- **Minimal DOM Manipulation**: Batch updates for better performance
- **CSS Hardware Acceleration**: Transform3d for smooth animations
- **Debounced Search**: Optimized search functionality

### API Optimization
- **Efficient Queries**: Firestore queries optimized for speed
- **Caching**: Browser caching of static assets
- **Compression**: Gzip compression on Vercel

## 🔐 Security

### Frontend Security
- **XSS Prevention**: All user input is escaped
- **Input Validation**: Client-side validation for all forms
- **HTTPS**: Vercel automatically provides SSL certificates

### Backend Security
- **Firebase Rules**: Database access restricted via rules
- **Environment Variables**: Sensitive data stored securely
- **CORS Headers**: Proper Cross-Origin configuration

## 🚀 Deployment

### Automatic Deployment
1. **Git Push**: Every push to main branch triggers new deployment
2. **Build Process**: Vercel automatically builds frontend and API
3. **Environment**: Production environment with Firebase configuration

### Manual Deployment
```bash
# 1. Install Vercel CLI
npm i -g vercel

# 2. Login to Vercel
vercel login

# 3. Deploy
vercel --prod
```

## 🔧 Development Setup

### Prerequisites
- **Node.js** (for development tools)
- **Python 3.9+** (for local API testing)
- **Firebase Account** (for database)
- **Vercel Account** (for deployment)

### Local Development
```bash
# 1. Clone repository
git clone https://github.com/Gasfornuis/Kitchen-chat.git
cd Kitchen-chat

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Setup environment variables
# FIREBASE_SERVICE_ACCOUNT='{...json...}'
# FIREBASE_SECRET='your-secret'

# 4. Start local server
vercel dev
```

### Environment Variables
```bash
# Vercel Environment Variables
FIREBASE_SERVICE_ACCOUNT='{"type":"service_account",...}'
FIREBASE_SECRET='your-firebase-secret-key'
```

## 📊 Browser Support

### Fully Supported
- **Chrome** 80+
- **Firefox** 75+
- **Safari** 13+
- **Edge** 80+

### Basic Functionality
- **IE 11**: Basic chat functionality (without modern CSS effects)
- **Older mobile browsers**: Core functionality works

## 🔄 API Documentation

### Subjects Endpoint (`/api/subjects`)

#### GET /api/subjects
Retrieves all topics, sorted by creation date (newest first).

**Response:**
```json
[
  {
    "id": "subject-id",
    "Title": "Topic title",
    "CreatedAt": "2025-09-18T19:30:00Z",
    "CreatedBy": "Username"
  }
]
```

#### POST /api/subjects
Creates a new topic.

**Request Body:**
```json
{
  "Title": "New topic",
  "CreatedBy": "Your name"
}
```

### Posts Endpoint (`/api/posts`)

#### GET /api/posts?SubjectId={id}
Retrieves all messages for a specific topic.

**Response:**
```json
[
  {
    "id": "message-id",
    "Content": "Message content",
    "CreatedAt": "2025-09-18T19:35:00Z",
    "PostedBy": "Username",
    "SubjectId": "/subjects/subject-id"
  }
]
```

#### POST /api/posts
Send a new message.

**Request Body:**
```json
{
  "Content": "Your message here",
  "SubjectId": "subject-id",
  "PostedBy": "Your name"
}
```

## 🎯 Future Features

### V2.0 Roadmap
- [ ] **User Accounts**: Authentication and profiles
- [ ] **Real-time WebSocket**: Live updates without polling
- [ ] **File Uploads**: Share images and documents
- [ ] **Emoji Support**: Reactions and emoji picker
- [ ] **Dark Mode**: Complete dark theme implementation
- [ ] **Push Notifications**: Browser notifications for new messages
- [ ] **Message Threading**: Reply to specific messages
- [ ] **User Status**: Online/offline indicators

### V2.1 Extensions
- [ ] **Admin Panel**: Moderation tools
- [ ] **Message Search**: Search through message history
- [ ] **Export Function**: Download chat history
- [ ] **Integrations**: Slack, Discord webhooks
- [ ] **Mobile App**: PWA to native app

## 🐛 Known Issues

- **Message Polling**: Messages refresh every 30 seconds (not real-time)
- **Offline Mode**: Limited functionality without internet connection
- **Long Messages**: No support for multi-line messages

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! See our contributing guidelines:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/AmazingFeature`)
3. **Commit** your changes (`git commit -m 'Add some AmazingFeature'`)
4. **Push** to the branch (`git push origin feature/AmazingFeature`)
5. **Open** a Pull Request

## 👥 Team

- **Lead Developer**: [Gasfornuis](https://github.com/Gasfornuis)
- **Frontend Design**: Modern web standards
- **Backend**: Python serverless architecture

## 📞 Support

For questions and support:
- **GitHub Issues**: [Create an issue](https://github.com/Gasfornuis/Kitchen-chat/issues)
- **Discussion**: [GitHub Discussions](https://github.com/Gasfornuis/Kitchen-chat/discussions)

---

**Kitchen Chat** - Where culinary conversations come together! 🍳✨