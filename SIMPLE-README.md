# Kitchen Chat - Simple Version

Een eenvoudige, ouderwetse versie van Kitchen Chat met minimale CSS maar volledige functionaliteit.

## 🚀 Functies

- **Real-time berichten** - Live updates van nieuwe berichten
- **Gespreksbeheer** - Maak en beheer gesprekken  
- **Zoekfunctie** - Zoek door gesprekken
- **Gebruikersvriendelijk** - Eenvoudige, schone interface
- **Responsief** - Werkt op desktop en mobiel
- **Offline detectie** - Toont verbindingsstatus

## 📁 Bestanden

### Hoofdbestanden
- `simple.html` - Hoofdpagina met eenvoudige structuur
- `simple-styles.css` - Minimale CSS styling
- `simple-script.js` - Kernfunctionaliteit in JavaScript

### Backend API's
De simple versie gebruikt dezelfde backend API's als de hoofdversie:
- `/api/subjects` - Gesprekken ophalen/maken
- `/api/posts` - Berichten ophalen/versturen

## 🎨 Design Filosofie

**Eenvoud boven alles:**
- Geen complexe animaties of effecten
- Minimale CSS (slechts basisstijlen)
- Schone, leesbare code
- Focus op functionaliteit
- Snelle laadtijd

## 🛠️ Technische Details

### HTML Structuur
```html
<!DOCTYPE html>
<html>
<head>
    <title>Kitchen Chat - Simple Version</title>
    <link rel="stylesheet" href="simple-styles.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>Kitchen Chat</h1>
            <button id="newSubjectBtn">+ New Conversation</button>
        </header>
        <!-- Rest van de structuur -->
    </div>
</body>
</html>
```

### CSS Kenmerken
- **Basis kleuren:** Blauw (#4a90e2) en grijs tinten
- **Simpele layout:** Flexbox voor basis positioning
- **Minimale effecten:** Alleen hover states
- **Responsive:** Eenvoudige media queries

### JavaScript Functies
```javascript
class SimpleKitchenChat {
    // Kern functionaliteit:
    - loadSubjects()      // Gesprekken laden
    - loadMessages()      // Berichten laden  
    - sendMessage()       // Bericht versturen
    - createSubject()     // Nieuw gesprek maken
    - startPolling()      // Real-time updates
}
```

## 🚀 Installatie & Gebruik

### Direct gebruiken
1. Open `simple.html` in je browser
2. Maak een nieuw gesprek
3. Begin met chatten!

### Lokale ontwikkeling
```bash
# Clone de repository
git clone https://github.com/Gasfornuis/Kitchen-chat.git
cd Kitchen-chat

# Open simple.html in je browser
open simple.html
# of
start simple.html
```

### Met backend
Voor volledige functionaliteit heb je de backend API's nodig:
```bash
# Start de Python backend
vercel dev
# of
python -m http.server 8000
```

## 📱 Browser Ondersteuning

**Volledig ondersteund:**
- Chrome 60+
- Firefox 55+
- Safari 11+
- Edge 79+

**Basis functionaliteit:**
- Oudere browsers via graceful degradation

## 🎯 Gebruik Cases

**Perfect voor:**
- **Eenvoudige chat** - Basis communicatie
- **Team overleg** - Snelle discussies
- **Projectcommunicatie** - Georganiseerde gesprekken
- **Leren** - Begrijpen van de basis functionaliteit
- **Oudere systemen** - Minimale resource vereisten

## 🔧 Aanpassingen

### Kleuren wijzigen
```css
/* In simple-styles.css */
header {
    background-color: #jouw-kleur; /* Verander hoofdkleur */
}

.subject-item.active {
    background-color: #jouw-kleur; /* Actieve item kleur */
}
```

### Functionaliteit uitbreiden
```javascript
// In simple-script.js
class SimpleKitchenChat {
    // Voeg nieuwe methode toe
    jouwNieuweFunctie() {
        // Jouw code hier
    }
}
```

## 📊 Prestaties

**Laadtijd:** < 1 seconde  
**CSS Grootte:** ~8KB  
**JavaScript Grootte:** ~16KB  
**Totale Grootte:** ~28KB

## 🔄 Updates Ontvangen

- **Polling interval:** 5 seconden
- **Automatische refresh** bij verbinding herstellen
- **Toast notificaties** voor nieuwe berichten

## 📋 Toetsenbord Shortcuts

| Shortcut | Actie |
|----------|-------|
| `Enter` | Bericht versturen |
| `Ctrl + N` | Nieuw gesprek |
| `Escape` | Modal sluiten |

## 🐛 Probleemoplossing

### Berichten laden niet
1. Controleer internetverbinding
2. Controleer of backend draait
3. Open browser console voor foutmeldingen

### Gesprekken niet zichtbaar
1. Vernieuw de pagina (F5)
2. Controleer of er gesprekken bestaan in database

### Styling problemen
1. Hard refresh (Ctrl+F5)
2. Controleer of `simple-styles.css` laadt

## 🚀 Deployment

### Vercel (Aanbevolen)
```bash
vercel --prod
```

### Statische hosting
1. Upload `simple.html`, `simple-styles.css`, `simple-script.js`
2. Configureer server voor API endpoints

## 🔒 Beveiliging

**Ingebouwde bescherming:**
- HTML escaping voor XSS preventie
- Input validatie
- HTTPS via Vercel

## 📞 Support

- **GitHub Issues:** Voor bugs en features
- **Discussies:** Voor vragen en hulp
- **Wiki:** Voor documentatie

## 📜 Licentie

MIT License - Vrij te gebruiken voor persoonlijke en commerciële doeleinden.

---

## Verschil met Hoofdversie

| Feature | Hoofdversie | Simple Versie |
|---------|-------------|----------------|
| **Design** | Modern glasmorphism | Basis styling |
| **CSS** | 44KB+ | 8KB |
| **JavaScript** | 64KB+ | 16KB |
| **Animaties** | Uitgebreid | Minimaal |
| **Features** | Voice, files, emoji | Tekst berichten |
| **Loading** | Fancy loading screen | Direct |
| **Browser support** | Modern browsers | Breed support |

**De simple versie behoud alle kernfunctionaliteit met een fractie van de code!**