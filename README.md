# Kitchen Chat 🍳💬

Een moderne, real-time chat applicatie voor keuken discussies, gebouwd met Python (Flask/Vercel) backend en vanilla JavaScript frontend.

## 🌟 Features

### ✨ Gebruikersinterface
- **Modern Design**: Gradient backgrounds, glasmorphism effecten, en smooth animaties
- **Responsive Layout**: Werkt perfect op desktop, tablet, en mobiele apparaten
- **Dark Mode Ready**: Voorbereiding voor toekomstige dark mode implementatie
- **Real-time Updates**: Automatische refresh van berichten en onderwerpen

### 💬 Chat Functionaliteit
- **Onderwerpen Maken**: Start nieuwe gesprekken met aangepaste titels
- **Real-time Berichten**: Instant messaging met directe feedback
- **Gebruikersnamen**: Personalisatie met opgeslagen gebruikersvoorkeuren
- **Zoekfunctie**: Vind snel specifieke onderwerpen
- **Auto-refresh**: Berichten worden automatisch ververst elke 30 seconden

### 🔧 Technische Features
- **Offline Detectie**: Meldt internetverbindingsstatus
- **Loading States**: Duidelijke feedback tijdens API calls
- **Error Handling**: Gebruiksvriendelijke foutmeldingen
- **PWA Ready**: Service Worker ondersteuning (uitbreidbaar)
- **Toegankelijkheid**: Keyboard navigation en screen reader support

## 🚀 Live Demo

**Frontend URL**: [kitchen-chat.vercel.app](https://kitchen-chat.vercel.app)

## 📁 Project Structuur

```
Kitchen-chat/
├── index.html          # Hoofd HTML bestand
├── styles.css          # Moderne CSS styling
├── script.js           # Frontend JavaScript logica
├── vercel.json         # Vercel configuratie
├── requirements.txt    # Python dependencies
├── api/
│   ├── posts.py       # API voor berichten
│   └── subjects.py    # API voor onderwerpen
└── README.md          # Deze documentatie
```

## 🛠 Technology Stack

### Frontend
- **HTML5**: Semantische markup met moderne structuur
- **CSS3**: 
  - Custom CSS properties (variabelen)
  - Flexbox en Grid layouts
  - CSS animations en transitions
  - Responsive design met media queries
  - Glassmorphism effecten
- **JavaScript (ES6+)**:
  - Modern class-based architectuur
  - Async/await voor API calls
  - LocalStorage voor gebruikersvoorkeuren
  - Event delegation voor performance

### Backend
- **Python**: Serverless functions op Vercel
- **Firebase Firestore**: NoSQL database voor berichten en onderwerpen
- **Firebase Admin SDK**: Beveiligde database toegang

### Deployment
- **Vercel**: Hosting voor frontend en API
- **Firebase**: Cloud database service

## 🎨 Design Systeem

### Kleurenpalet
```css
/* Primaire kleuren */
--primary-gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
--primary-blue: #667eea;
--primary-purple: #764ba2;

/* Grijstinten */
--gray-900: #2d3748;
--gray-600: #718096;
--gray-400: #a0aec0;
--gray-100: #f7fafc;

/* Status kleuren */
--success: #38a169;
--error: #e53e3e;
--warning: #d69e2e;
```

### Typografie
- **Font**: Inter (fallback naar systeem fonts)
- **Weights**: 400 (regular), 500 (medium), 600 (semibold), 700 (bold)
- **Responsive font sizes**: Schaalbaar voor alle schermformaten

### Spacing Systeem
- **Base unit**: 0.25rem (4px)
- **Scale**: 0.5rem, 0.75rem, 1rem, 1.5rem, 2rem, etc.
- **Consistent margins en padding** door hele applicatie

## 📱 Responsive Design

### Desktop (1200px+)
- **Sidebar**: 320px vaste breedte voor onderwerpen
- **Chat Area**: Flexibele breedte voor berichten
- **Two-column layout**: Optimaal voor grote schermen

### Tablet (768px - 1199px)
- **Sidebar**: Volledige breedte, 40vh hoogte
- **Chat Area**: Volledige breedte, 60vh hoogte
- **Stacked layout**: Verticale organisatie

### Mobile (< 768px)
- **Single column**: Alle elementen op volledige breedte
- **Touch-friendly**: Grotere knoppen en input velden
- **Optimized spacing**: Aangepaste margins en padding

## ⚡ Performance Optimalisaties

### Frontend
- **Lazy Loading**: Berichten worden alleen geladen wanneer nodig
- **Event Delegation**: Efficiënte event handling
- **Minimal DOM Manipulation**: Batch updates voor betere performance
- **CSS Hardware Acceleration**: Transform3d voor smooth animaties
- **Debounced Search**: Optimalized zoekfunctionaliteit

### API Optimalisatie
- **Efficient Queries**: Firestore queries geoptimaliseerd voor snelheid
- **Caching**: Browser caching van statische assets
- **Compression**: Gzip compressie op Vercel

## 🔐 Beveiliging

### Frontend Beveiliging
- **XSS Preventie**: Alle gebruikersinput wordt ge-escaped
- **Input Validatie**: Client-side validatie voor alle formulieren
- **HTTPS**: Vercel zorgt automatisch voor SSL certificaten

### Backend Beveiliging
- **Firebase Rules**: Database toegang beperkt via regels
- **Environment Variables**: Gevoelige data veilig opgeslagen
- **CORS Headers**: Juiste Cross-Origin configuratie

## 🚀 Deployment

### Automatische Deployment
1. **Git Push**: Elke push naar main branch triggert nieuwe deployment
2. **Build Process**: Vercel bouwt automatisch frontend en API
3. **Environment**: Productie environment met Firebase configuratie

### Handmatige Deployment
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
- **Node.js** (voor development tools)
- **Python 3.9+** (voor lokale API testing)
- **Firebase Account** (voor database)
- **Vercel Account** (voor deployment)

### Lokale Development
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

### Volledig Ondersteund
- **Chrome** 80+
- **Firefox** 75+
- **Safari** 13+
- **Edge** 80+

### Basis Functionaliteit
- **IE 11**: Basis chat functionaliteit (zonder moderne CSS effecten)
- **Oudere mobiele browsers**: Core functionaliteit werkt

## 🔄 API Documentatie

### Subjects Endpoint (`/api/subjects`)

#### GET /api/subjects
Haalt alle onderwerpen op, gesorteerd op aanmaakdatum (nieuwste eerst).

**Response:**
```json
[
  {
    "id": "subject-id",
    "Title": "Onderwerp titel",
    "CreatedAt": "2025-09-18T19:30:00Z",
    "CreatedBy": "Gebruikersnaam"
  }
]
```

#### POST /api/subjects
Maakt een nieuw onderwerp aan.

**Request Body:**
```json
{
  "Title": "Nieuw onderwerp",
  "CreatedBy": "Jouw naam"
}
```

### Posts Endpoint (`/api/posts`)

#### GET /api/posts?SubjectId={id}
Haalt alle berichten voor een specifiek onderwerp op.

**Response:**
```json
[
  {
    "id": "message-id",
    "Content": "Bericht inhoud",
    "CreatedAt": "2025-09-18T19:35:00Z",
    "PostedBy": "Gebruikersnaam",
    "SubjectId": "/subjects/subject-id"
  }
]
```

#### POST /api/posts
Verzend een nieuw bericht.

**Request Body:**
```json
{
  "Content": "Je bericht hier",
  "SubjectId": "subject-id",
  "PostedBy": "Jouw naam"
}
```

## 🎯 Toekomstige Features

### V2.0 Roadmap
- [ ] **Gebruikersaccounts**: Authenticatie en profielen
- [ ] **Real-time WebSocket**: Live updates zonder polling
- [ ] **Bestand Uploads**: Afbeeldingen en documenten delen
- [ ] **Emoji Support**: Reacties en emoji picker
- [ ] **Dark Mode**: Volledige dark theme implementatie
- [ ] **Push Notifications**: Browser notificaties voor nieuwe berichten
- [ ] **Message Threading**: Antwoorden op specifieke berichten
- [ ] **Gebruikers Status**: Online/offline indicatoren

### V2.1 Uitbreidingen
- [ ] **Admin Panel**: Moderatie tools
- [ ] **Message Search**: Zoeken in bericht geschiedenis
- [ ] **Export Functie**: Chat geschiedenis downloaden
- [ ] **Integraties**: Slack, Discord webhooks
- [ ] **Mobile App**: PWA naar native app

## 🐛 Bekende Issues

- **Message Polling**: Berichten worden elke 30 seconden ververst (geen real-time)
- **Offline Mode**: Beperkte functionaliteit zonder internetverbinding
- **Long Messages**: Geen ondersteuning voor multi-line berichten

## 📄 License

MIT License - zie [LICENSE](LICENSE) bestand voor details.

## 🤝 Contributing

Contributies zijn welkom! Zie onze contributing guidelines:

1. **Fork** het repository
2. **Create** een feature branch (`git checkout -b feature/AmazingFeature`)
3. **Commit** je wijzigingen (`git commit -m 'Add some AmazingFeature'`)
4. **Push** naar de branch (`git push origin feature/AmazingFeature`)
5. **Open** een Pull Request

## 👥 Team

- **Lead Developer**: [Gasfornuis](https://github.com/Gasfornuis)
- **Frontend Design**: Modern web standards
- **Backend**: Python serverless architecture

## 📞 Support

Voor vragen en ondersteuning:
- **GitHub Issues**: [Create an issue](https://github.com/Gasfornuis/Kitchen-chat/issues)
- **Discussion**: [GitHub Discussions](https://github.com/Gasfornuis/Kitchen-chat/discussions)

---

**Kitchen Chat** - Waar culinaire gesprekken samenkomen! 🍳✨