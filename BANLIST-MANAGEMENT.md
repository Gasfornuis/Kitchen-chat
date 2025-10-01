# Banlist Management System

Dit document beschrijft het banlist systeem voor Kitchen Chat dat is geïmplementeerd om ongewenste gebruikers te beheren.

## Overzicht

Het banlist systeem stelt administrators in staat om gebruikers te bannen en hun toegang tot de chat service te beperken. Gebannede gebruikers kunnen niet inloggen of registreren.

## Admin Gebruikers

Momenteel zijn de volgende gebruikers geautoriseerd als administrators:
- `daan25`
- `gasfornuis`

Administrators hebben toegang tot:
- 📢 **Announcements beheer** (aanmaken/verwijderen)
- 🚫 **Banlist beheer** (bannen/ontbannen van gebruikers)
- **Quick ban** functionaliteit in de online gebruikers lijst

## Banlist Functionaliteit

### Voor Administrators

#### Toegang tot Banlist
1. Login als administrator
2. Klik op de "🚫 Banlist" knop in de header (alleen zichtbaar voor admins)
3. Het banlist management venster opent

#### Een gebruiker bannen
1. Open het banlist venster
2. Vul de vereiste velden in:
   - **Username**: De gebruikersnaam om te bannen (verplicht)
   - **Display Name**: De weergavenaam (optioneel, wordt username als leeg)
   - **Reason**: Reden voor de ban (verplicht, max 500 karakters)
3. Klik "Ban User"
4. Bevestig de actie

#### Quick Ban
1. Ga naar de "Online Users" lijst rechts op het scherm
2. Klik op de 🚫 knop naast een gebruiker (alleen zichtbaar voor admins)
3. Voer een reden in wanneer gevraagd
4. De gebruiker wordt direct gebanned

#### Een gebruiker ontbannen
1. Open het banlist venster
2. Zoek de gebruiker in de "Banned Users" lijst
3. Klik "Unban" naast de gebruiker
4. Bevestig de actie

### Voorbeeld: JeffreyEpstein bannen

Om de gebruiker "JeffreyEpstein" te bannen:

1. **Via Banlist Modal:**
   - Open "🚫 Banlist"
   - Username: `JeffreyEpstein`
   - Reason: `Inappropriate username`
   - Klik "Ban User"

2. **Via Quick Ban:**
   - Zoek "JeffreyEpstein" in de online gebruikers lijst
   - Klik 🚫 knop
   - Voer reden in: `Inappropriate username`

## Technische Details

### API Endpoints

#### `/api/banlist` (GET)
- **Beschrijving**: Haal lijst van gebannede gebruikers op
- **Authenticatie**: Vereist admin rechten
- **Response**: JSON array van ban records

#### `/api/banlist` (POST)
- **Beschrijving**: Ban een gebruiker
- **Authenticatie**: Vereist admin rechten
- **Body**: `{username, displayName, reason}`
- **Response**: Success/error message

#### `/api/banlist` (DELETE)
- **Beschrijving**: Ontban een gebruiker
- **Authenticatie**: Vereist admin rechten
- **Body**: `{banId}`
- **Response**: Success/error message

### Database Schema (Firestore)

#### BannedUsers Collection
```json
{
  "username": "gebruikersnaam (lowercase)",
  "displayName": "Weergavenaam",
  "reason": "Reden voor ban",
  "bannedBy": "Admin die de ban heeft uitgevoerd",
  "createdAt": "Timestamp",
  "active": true,
  "unbannedBy": "Admin die ontban heeft uitgevoerd (optioneel)",
  "unbannedAt": "Timestamp (optioneel)"
}
```

### Security Features

1. **Server-side validatie**: Alle ban controles gebeuren server-side
2. **Rate limiting**: Beperkt aantal API calls per IP
3. **Admin controle**: Dubbele controle op client en server voor admin rechten
4. **Sessie controle**: Gebannede gebruikers worden direct uitgelogd
5. **Logging**: Alle ban acties worden gelogd voor audit trail
6. **Admin bescherming**: Admin gebruikers kunnen niet gebanned worden

### Banlist Controles

Het systeem controleert op bans tijdens:
1. **Login**: Gebannede gebruikers kunnen niet inloggen
2. **Registratie**: Gebannede usernames kunnen niet geregistreerd worden
3. **Session verificatie**: Bestaande sessies van gebannede gebruikers worden beëindigd

## Beheer

### Een ban opheffen
1. Open banlist management
2. Zoek de gebruiker in de lijst
3. Klik "Unban"
4. De ban wordt gedeactiveerd (niet verwijderd voor audit trail)

### Banlist bekijken
Alleen administrators kunnen de banlist bekijken. De lijst toont:
- Username
- Display name (indien anders)
- Reden voor ban
- Datum/tijd van ban
- Welke admin de ban heeft uitgevoerd

## Best Practices

1. **Geef altijd een duidelijke reden** bij het bannen van gebruikers
2. **Controleer dubbel** voordat je een gebruiker bant
3. **Gebruik Quick Ban** voor snelle moderatie tijdens gesprekken
4. **Documenteer belangrijke bans** voor toekomstige referentie
5. **Controleer regelmatig** of bans nog relevant zijn

## Troubleshooting

### Banlist knop niet zichtbaar
- Controleer of je ingelogd bent als admin gebruiker
- Ververs de pagina om admin status opnieuw te laden

### API errors
- Controleer netwerk connectie
- Controleer of Firebase correct geconfigureerd is
- Bekijk browser console voor gedetailleerde errors

### Gebruiker kan nog steeds inloggen na ban
- Controleer of de ban actief is in de database
- Gebruiker moet mogelijk opnieuw proberen in te loggen
- Bestaande sessies blijven actief tot verificatie

## Updates en Wijzigingen

- **v1.0** (01-10-2025): Initiële implementatie van banlist systeem
  - Basic ban/unban functionaliteit
  - Admin interface
  - Quick ban knoppen
  - Database integratie