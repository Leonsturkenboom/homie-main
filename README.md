# Homie Main

**Homie Main** is the central UX & orchestration layer of the Homie ecosystem for Home Assistant.

It is responsible for:
- Presence orchestration (GPS / WiFi / Motion / Calendar)
- User-configurable notifications
- Health & data-gap monitoring
- KPI visualization passthrough (power, energy, price)
- A clean, install-once / configure-later experience

This integration is designed to be:
- ✅ Wizard-only (no input_* helpers)
- ✅ HACS installable
- ✅ Installer-proof, user-friendly
- ✅ Scalable to multiple homes/sites

---

## ✨ Features

- Presence detection via:
  - GPS (persons / device_trackers)
  - WiFi (device_trackers)
  - Motion (binary_sensors)
  - Calendar (`calendar.homie`)
- Manual override logic (until next midnight)
- Push & notification management (user editable)
- Health warnings when data sources become unavailable
- KPI passthrough sensors for dashboards
- YAML dashboards & cards included

---

## 📦 Installation (HACS)

1. Open **HACS**
2. Add this repository as a **Custom Repository**
3. Category: **Integration**
4. Install **Homie Main**
5. Restart Home Assistant

---

## 🧙 Initial Setup (Installer)

After installation:
1. Go to **Settings → Devices & Services**
2. Add integration **Homie Main**
3. Follow the wizard:
   - Site name
   - Presence detection type (GPS / WiFi / Motion / Calendar)
   - Select relevant entities
   - Confirm

⚠️ **Presence mode is locked after installation**  
This is intentional and prevents accidental architectural changes.

---

## ⚙️ User Configuration (After Install)

Users can later change (without reinstalling):
- Notifications on/off
- Push notifications on/off
- Notification levels
- KPI entity mapping
- Notify target (`notify.notify` by default)

Via:
- **Settings → Devices & Services → Homie Main → Options**
- Or directly via exposed switch/select entities

---

## 🔔 Notifications

- Persistent notifications are always created (audit trail)
- Push notifications:
  - Default target: `notify.notify` (all apps)
  - Can be overridden via options
- Warnings are rate-limited (default: once per 6 hours)

Recommended (optional):
```yaml
notify:
  - platform: group
    name: homie_all_apps
    services:
      - service: mobile_app_phone_1
      - service: mobile_app_phone_2
