# Automatisk Förseningsersättning Movingo

Automatiskt system för att upptäcka tågförseningar och begära ersättning för Movingo-resenärer på sträckorna Stockholm C → Bålsta och Stockholm C → Uppsala.

## Översikt

Systemet:
1. **Övervakar** tågförseningar via Trafikverkets öppna API
2. **Beräknar** ersättningsrätt baserat på varje operatörs regler
3. **Förbereder** ersättningsanspråk med alla nödvändiga uppgifter
4. **Öppnar** operatörens formulär i webbläsaren för inskickning

## Stödda operatörer

| Operatör | Försening | Ersättning | Ansökningslänk |
|----------|-----------|------------|----------------|
| **UL** | 20–39 min | 50% | [ul.se](https://www.ul.se/kundservice/forseningsersattning/) |
| **UL** | 40–59 min | 75% | |
| **UL** | 60+ min | 100% | |
| **SL** | 20–59 min | 50% | [sl.se](https://sl.se/kundservice/forseningsersattning) |
| **SL** | 60+ min | 100% | |
| **Mälardalstrafik** (<150 km) | 20–39 min | 50% | [Mälardalstrafik](https://evf-regionsormland.preciocloudapp.net/trains) |
| **Mälardalstrafik** (<150 km) | 40–59 min | 75% | |
| **Mälardalstrafik** (<150 km) | 60+ min | 100% | |
| **SJ** (<150 km) | 20–59 min | 50% | [sj.se](https://www.sj.se/om-sj/regler-och-villkor/rattigheter-vid-forsening) |
| **SJ** (<150 km) | 60+ min | 100% | |

## Installation

```bash
pip install -r requirements.txt
```

## Användning

### Sök efter förseningar

```bash
python main.py poll
```

Kontrollerar Trafikverkets API efter aktuella förseningar >20 min på de övervakade sträckorna och sparar dem i `delay_log.json`.

### Visa väntande anspråk

```bash
python main.py status
```

Visar alla registrerade förseningar som ännu inte har anmälts, med operatör och ersättningsbelopp.

### Skicka in ersättningsanspråk

```bash
python main.py claim          # Visa instruktioner för varje anspråk
python main.py claim --auto   # Öppna operatörens formulär i webbläsaren
```

### Visa historik

```bash
python main.py history
```

### Kör fristående försöksökning (senaste 30 dagarna)

```bash
python find_delays.py
```

## Automatisk övervakning (cron)

Lägg till i crontab för att polla var 5:e minut:

```bash
crontab -e
```

```
*/5 * * * * cd /path/to/Automatisk-F-rseningsers-ttning-Movingo && python main.py poll >> poll.log 2>&1
```

## Projektstruktur

```
├── main.py                 # CLI-orkestrator (poll/status/claim/history)
├── delay_monitor.py        # Pollar Trafikverket och lagrar förseningar
├── compensation_rules.py   # Ersättningsregler per operatör
├── claim_submitter.py      # Förbereder och skickar anspråk
├── fetch_train_data.py     # Grundläggande Trafikverket API-klient
├── find_delays.py          # Fristående sökning av historiska förseningar
├── requirements.txt        # Python-beroenden
└── delay_log.json          # Loggfil med upptäckta förseningar (genereras)
```

## Begränsningar

- **Trafikverkets API** behåller bara ~3 dagars historik för TrainAnnouncement-data. Därför behöver `poll` köras regelbundet för att bygga upp en egen historik.
- **Automatisk inskickning** kräver Selenium (`pip install selenium`) och en webbläsardrivrutin (ChromeDriver). Utan detta visas instruktioner för manuell inskickning.
- **Operatörsidentifiering** baseras på tågnummermönster och kan behöva justeras för ovanliga tågnummer.

## API-nyckel

Projektet använder Trafikverkets öppna API. Nuvarande nyckel finns i koden. Skaffa en egen gratis på [trafikverket.se](https://api.trafikinfo.trafikverket.se/).
