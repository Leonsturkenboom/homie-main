# Product Requirements Document - Homie Main

## 1. Scope, Goal & Value

homie_main is the **UX + orchestration** block for Homie. It does not calculate deep energy flows; it aggregates outputs from other blocks and device-layer entities into:

- A **Main dashboard view** (presence + energy + solar + price + notifications)
- A **Config board view** (customer-tunable settings, REST-controllable)
- A **Notification board view** (filtered, tagged, categorized)
- A **Status & health layer** (data-gap warnings, missing inputs, system confidence)

### Value:
- One "home screen" that always works
- Consistent presence + schedule status used by other blocks
- Customer can tune behavior post-install without re-running wizard

### Success criteria (must-pass):
- Works even if PV/forecast/price blocks are absent (graceful degradation)
- UI never breaks on unknown/unavailable/None
- All "customer-tunable" parameters are entities (helpers), so external app can update via REST

### Out of scope:
- Most notification generation (delegated to other blocks)
- In-depth calculations (handled within source blocks)
- Contract logic (energy_price), PV optimization (pv_system), battery/EV/HP scheduling

---

## 2. Functional Requirements

### INPUT

| ID | What | Unit | Note |
|----|------|------|------|
| A | Presence localisation detection type | GPS/WiFi/Motion/Calendar | Configurable in wizard |
| B | GPS based presence detection | device_tracker.* | Multiple devices, interval per hour |
| C | Home GPS zone | zone.home coordinates | Auto-identified during config |
| D | GPS distance around home | 20-10000m | Standard 100m |
| E | WiFi device presence | IP & name | Multiple devices, interval 15 min |
| F | Motion based presence detector | binary_sensor.motion_* | Multiple devices, interval per hour |
| G | Calendar based presence detector | calendar.homie | Reads Holiday/Guests from title/description |
| H | Total power use | W or kW | sensor.ec_total_power_use |
| I | Total daily energy use | Wh or kWh | sensor.ec_net_energy_use_on_site_day |
| J | Total production | W or kW | sensor.ec_produced_power_day |
| K | Total forecasted use | Wh or kWh | sensor.ef_net_energy_forecast |
| L | Total daily production | Wh or kWh | sensor.ec_produced_energy_day |
| M | Forecast solar | - | sensor.es_solar_production_forecast |
| N | Purchase price | EUR/kWh | sensor.ep_purchase_price |
| O | Notifications tagged with Homie | - | Aggregated from modules |
| P | Email | - | Email(s) for alarms |
| Q | Site name | input_text.hm_site_name | Default: Home |

---

### OUTPUT

| # | Type | Name | What | Category |
|---|------|------|------|----------|
| 1 | input_selector | input_select.hm_schedule_status | Presence status | Presence |
| 2 | sensor helper | nighttime | 1 if night, 0 if day | - |
| 3 | sensor helper | sensor.hm_price_series_24h | 24h price data | Price |
| 4 | Visual | input_select.hm_schedule_status | Shows/changes presence | Presence |
| 5 | Visual | Use | Current/min/max energy use 24h | Energy |
| 6 | Visual | Solar | Current/min/max production 24h | Energy |
| 7 | Visual | Price | Current/min/max price 24h | Price |
| 8 | Visual | Notification board | All Homie-tagged notifications | Notifications |
| 9 | Email notifications | - | Warnings/alerts via email | Notifications |
| 10 | Push notifications | - | Within HA and app | Notifications |
| **11** | **Notification** | **sensor.hm_warning_data_gap_presence** | **Data unavailable warning** | **Presence** |
| **12** | **Notification** | **sensor.hm_warning_data_gap_calendar** | **Calendar data unavailable** | **Presence** |
| **13** | **Notification** | **sensor.hm_warning_data_gap_main** | **Main KPI data unavailable** | **Main** |
| 14 | Visual | Config board | All input helpers overview | Config |
| 15 | Visual | Config wizard | Installation wizard | Config |

---

## 3. Outputs 11-12-13: Data Gap Notifications

### Output 11: sensor.hm_warning_data_gap_presence
- **Trigger:** Any of B/E/F (GPS/WiFi/Motion) unavailable for > 1 hour
- **Message:** "Waarschuwing: 1 of meerdere data voor presence is onbeschikbaar"
- **Category:** Presence

### Output 12: sensor.hm_warning_data_gap_calendar
- **Trigger:** Calendar entity (G) unavailable for > 1 hour
- **Message:** "Waarschuwing: 1 of meerdere data input is onbeschikbaar"
- **Category:** Presence

### Output 13: sensor.hm_warning_data_gap_main
- **Trigger:** Any of H-M (power/energy/forecast/price) unavailable for > 1 hour
- **Message:** "Waarschuwing: 1 of meerdere data input is onbeschikbaar"
- **Category:** Main

---

## 4. Visualizations

### PRD Colors:
- **Use:** rgba(127, 17, 224, 1) - Purple
- **Solar:** rgba(233, 188, 5, 1) - Yellow
- **Price:** rgba(224, 75, 30, 1) - Orange

### Dashboard Components:
- Heading with icon mdi:home-analytics
- Schedule + Eenheid selector (2 columns)
- Three graphs horizontal (Use, Solar, Price)
- Notifications board below

---

## 5. Config Wizard (Output 15)

### Block 1: General
- Site name
- Email(s) beheerder
- Push notifications (general/alerts/warnings)
- Mail notifications (warnings/alerts)
- Presence detection yes/no

### Block 2: Presence Methods
- Mobile GPS yes/no
- WiFi connection yes/no
- Motion sensors yes/no
- Calendar plug-in yes/no

### Block 3: Presence Configuration
- GPS entities + distance (10-5000m)
- WiFi entities
- Motion sensors
- Calendar entities

### Block 4: KPI Mapping
- Power use sensor
- Day energy sensor
- Solar power sensor
- Solar energy sensor
- Forecast sensors
- Purchase price sensor

---

## 6. Config Board (Output 14)

### Notifications
- Push: General/Warnings/Alerts on/off
- Mail: Warnings/Alerts on/off

### Presence Detection
- Mobile GPS on/off
- WiFi connection on/off
- Motion detection on/off
- Calendar plug-in on/off

---

## 7. Future Versions
- Integrate security system
- Integrate GPS location from Homie app
