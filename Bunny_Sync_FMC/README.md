# wingmen-codes

Monorepo med WingPy-baserede automationsscripts til Cisco FMC.

---

## Projekter

### 🐰 Bunny_Sync_FMC

Synkroniserer BunnyCDN edge server IP-adresser til en Cisco FMC Dynamic Object.

#### Scripts

| Script | Beskrivelse |
|--------|-------------|
| `bunny_to_FMC.py` | **Automatiseret version** - Læser konfiguration fra `.env` fil. Ideel til scheduled jobs / cron. |
| `bunny_to_FMC-interaktiv.py` | **Interaktiv version** - Prompter for alle værdier ved kørsel. God til test og debugging. |
| `FMC_dynObj.py` | **Debug værktøj** - Lister alle Dynamic Objects på FMC. |

#### Hvad gør scriptet?

1. Henter aktuelle IPv4 (og evt. IPv6) adresser fra BunnyCDN's API
2. Opretter/finder Dynamic Object på FMC
3. Sammenligner nuværende mappings med Bunny's liste
4. Tilføjer nye og fjerner forældede IP'er
5. Ingen deploy nødvendig - Dynamic Objects opdateres on-the-fly

---

## Opsætning efter `git pull`

```bash
# 1. Clone repository
git clone https://github.com/IronKeyVault/wingmen-codes.git
cd wingmen-codes

# 2. Gå ind i projekt-mappen
cd Bunny_Sync_FMC

# 3. Opret virtuelt miljø
python -m venv .venv

# 4. Aktiver miljøet
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

# 5. Installer afhængigheder
pip install -r requirements.txt

# 6. Opret .env fil fra template
cp .env.example .env

# 7. Rediger .env med dine FMC credentials
nano .env   # eller brug din foretrukne editor
```

---

## Kørsel

### Automatiseret (til cron/scheduled jobs)
```bash
cd Bunny_Sync_FMC
source .venv/bin/activate
python bunny_to_FMC.py
```

### Interaktiv (til test)
```bash
cd Bunny_Sync_FMC
source .venv/bin/activate
python bunny_to_FMC-interaktiv.py
```

---

## Miljøvariabler (.env)

| Variabel | Beskrivelse | Eksempel |
|----------|-------------|----------|
| `WINGPY_FMC_BASE_URL` | FMC server URL | `https://fmc.example.com` |
| `WINGPY_FMC_USERNAME` | FMC brugernavn | `admin` |
| `WINGPY_FMC_PASSWORD` | FMC password | `your_password` |
| `FMC_DYNAMIC_NAME` | Navn på Dynamic Object | `BunnyCDN_Dynamic` |
| `INCLUDE_IPV6` | Inkluder IPv6 adresser | `false` |
| `VERIFY_SSL` | Verificer SSL certifikat | `false` |
| `DRY_RUN` | Simuler uden ændringer | `false` |

---

## Krav

- Python 3.10+
- Netværksadgang til FMC og BunnyCDN API
- FMC bruger med rettigheder til at oprette/redigere Dynamic Objects

---

## FMC Konfiguration

### Brug af Dynamic Object i firewall-regler

Scriptet opretter automatisk et Dynamic Object (f.eks. `BunnyCDN_Dynamic`) på FMC. For at det har effekt, skal du **manuelt oprette en firewall-regel** der bruger dette objekt:

1. **Log ind på FMC** → Policies → Access Control
2. **Opret/rediger en Access Control Policy**
3. **Tilføj en ny regel:**
   - **Source/Destination**: Vælg "Dynamic Objects" → `BunnyCDN_Dynamic`
   - **Action**: Allow/Trust (afhængig af dit behov)
   - **Logging**: Aktiver efter behov
4. **Deploy** policyen til dine firewalls

> ⚠️ **Vigtigt**: Dynamic Objects opdateres automatisk uden deploy, men selve **firewall-reglen skal deployes** første gang den oprettes.

### Eksempel use case

Tillad trafik fra BunnyCDN edge servere til dine webservere:
```
Source: Dynamic Object "BunnyCDN_Dynamic"
Destination: Webserver network
Action: Allow
```

---

## Automatisk kørsel med Cron

Scriptet kører **én gang og afslutter** - det har ingen indbygget scheduler. Brug cron til at køre det automatisk:

### Opsætning af cron job

```bash
crontab -e
```

### Eksempler

**Kør hvert 5. minut:**
```cron
*/5 * * * * cd /path/to/wingmen-codes/Bunny_Sync_FMC && /path/to/wingmen-codes/Bunny_Sync_FMC/.venv/bin/python bunny_to_FMC.py >> /var/log/bunny_sync.log 2>&1
```

**Kør hver time:**
```cron
0 * * * * cd /path/to/wingmen-codes/Bunny_Sync_FMC && /path/to/wingmen-codes/Bunny_Sync_FMC/.venv/bin/python bunny_to_FMC.py >> /var/log/bunny_sync.log 2>&1
```

**Kør hver 6. time:**
```cron
0 */6 * * * cd /path/to/wingmen-codes/Bunny_Sync_FMC && /path/to/wingmen-codes/Bunny_Sync_FMC/.venv/bin/python bunny_to_FMC.py >> /var/log/bunny_sync.log 2>&1
```

**Kør én gang dagligt kl. 03:00:**
```cron
0 3 * * * cd /path/to/wingmen-codes/Bunny_Sync_FMC && /path/to/wingmen-codes/Bunny_Sync_FMC/.venv/bin/python bunny_to_FMC.py >> /var/log/bunny_sync.log 2>&1
```


> 💡 **Tip**: BunnyCDN's IP-liste ændrer sig sjældent - én gang dagligt eller hver 6. time er typisk nok.

### Tjek logs

```bash
tail -f /var/log/bunny_sync.log
```

