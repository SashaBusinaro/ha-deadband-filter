# ha-deadband-filter

[![Validate][validate-badge]][validate-url]
[![HACS Custom][hacs-badge]][hacs-url]
[![Release][release-badge]][release-url]
[![License][license-badge]][license-url]

[validate-badge]: https://img.shields.io/github/actions/workflow/status/SashaBusinaro/ha-deadband-filter/validate.yml?style=for-the-badge&label=Validate
[validate-url]: https://github.com/SashaBusinaro/ha-deadband-filter/actions/workflows/validate.yml
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge&logo=homeassistantcommunitystore&logoColor=white
[hacs-url]: https://www.hacs.xyz/docs/faq/custom_repositories/
[release-badge]: https://img.shields.io/github/v/release/SashaBusinaro/ha-deadband-filter?style=for-the-badge&color=blue
[release-url]: https://github.com/SashaBusinaro/ha-deadband-filter/releases
[license-badge]: https://img.shields.io/github/license/SashaBusinaro/ha-deadband-filter?style=for-the-badge
[license-url]: https://github.com/SashaBusinaro/ha-deadband-filter/blob/main/LICENSE

A lightweight, high-performance Home Assistant custom integration that creates a **deadband-filtered derived sensor** for high-frequency numeric sources (power meters, voltage, temperature, battery load).

It **reduces database writes to SQLite by 90–95%** by eliminating background jitter in memory, while maintaining instant reactivity on significant changes and preserving 100% compatibility with **Long-Term Statistics (LTS)**.

---

## Key Features

- **90–95% SQLite Write Reduction**: Raw fluctuations are filtered in memory; no database commit occurs unless thresholds are reached.
- **Immediate Peak Reactivity**: Significant spikes or drops are published instantly with zero delay.
- **Update Criteria (OR Logic)**:
  - **Absolute variation ($\Delta$)**: $|v_{\text{current}} - v_{\text{last}}| \ge \text{delta}$ (e.g. $\ge 40\,\text{W}$).
  - **Percentage variation (%)**: $\frac{|v_{\text{current}} - v_{\text{last}}|}{|v_{\text{last}}|} \ge \text{percentage}$ (e.g. $\ge 5\%$).
  - **Heartbeat timeout ($\Delta t$)**: Forces a write if no update has occurred for a preset duration (e.g. 5 minutes) to ensure continuous history graphs.
  - **Availability tracking**: Transitions between available and unavailable/unknown immediately mirror the source.
- **Automatic Metadata Inheritance (LTS Ready)**:
  - `unit_of_measurement` (e.g. `W`, `V`, `°C`)
  - `device_class` (e.g. `power`, `voltage`, `temperature`)
  - `state_class` (e.g. `measurement`)
  - `icon`
- **Dual Configuration**: Setup via **YAML** or via the **UI Helpers** interface with runtime reconfiguration via Options Flow.

---

## Installation

### Step 1: Install the Integration

**Prerequisites:** This integration requires Home Assistant 2026.8.0 or newer and [HACS](https://hacs.xyz/) (Home Assistant Community Store) to be installed.

Click the button below to open the integration directly in HACS:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=SashaBusinaro&repository=ha-deadband-filter&category=integration)

Then:

1. Click "Download" to install the integration
2. **Restart Home Assistant** (required after installation)

> [!NOTE]
> The My Home Assistant redirect will first take you to a landing page. Click the button there to open your Home Assistant instance.

<details>
<summary><strong>Manual Installation (Advanced)</strong></summary>

If you prefer not to use HACS:

1. Download the `custom_components/deadband_filter/` folder from this repository
2. Copy it to your Home Assistant's `custom_components/` directory
3. Restart Home Assistant

</details>

### Step 2: Configure the Integration

**Important:** Complete Step 1 and restart Home Assistant before proceeding.

#### Option 1: One-Click Setup

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=deadband_filter)

#### Option 2: Manual Setup (UI)

1. Go to **Settings** → **Devices & Services**
2. Click **"+ Add Integration"** (or go to **Helpers** → **"+ Create Helper"**)
3. Search for "Deadband Filter"
4. Follow the setup wizard

#### Option 3: YAML Configuration

Add the sensor platform under `sensor:` in your `configuration.yaml`:

```yaml
sensor:
  - platform: deadband_filter
    source: sensor.power_home_instant
    name: "Power Home Filtered"       # Optional (defaults to source name with 'Filtered' suffix)
    delta: 40                         # Optional (minimum absolute variation to publish)
    percentage: 5                     # Optional (minimum % variation, e.g. 5 for 5%)
    heartbeat: 00:05:00               # Optional (time period or seconds, e.g. 300)
    precision: 1                      # Optional (decimal rounding precision)
    unique_id: power_home_filtered    # Optional
```

---

## Maximizing Database Savings with Recorder

To achieve the full 90–95% reduction in disk I/O and SQLite storage, exclude the noisy raw source entity from your Home Assistant `recorder`:

```yaml
recorder:
  exclude:
    entities:
      - sensor.power_home_instant # Raw noisy sensor excluded from DB
```

The filtered sensor (`sensor.power_home_instant_filtered`) will record clean, deadband-filtered data into SQLite, and Home Assistant's statistics engine will automatically compile hourly and 5-minute Long-Term Statistics from it!

---

## Configuration Reference

| Parameter | Type | Required | Description |
|---|---|---|---|
| `source` | `string` | **Yes** | The entity ID of the numeric source sensor. |
| `name` | `string` | No | Custom friendly name. Defaults to `{Source Name} Filtered`. |
| `delta` | `float` | No | Minimum absolute difference $|v_{\text{current}} - v_{\text{last}}|$ to trigger a publish. |
| `percentage` | `float` | No | Minimum percentage difference to trigger a publish (e.g. `5` for 5%). |
| `heartbeat` | `time / int` | No | Maximum time before forcing an update (e.g. `00:05:00` or `300` seconds). |
| `precision` | `int` | No | Number of decimal places to round values to before filtering. |
| `unique_id` | `string` | No | Unique identifier for entity management in the UI registry. |

> [!NOTE]
> At least one of `delta`, `percentage`, or `heartbeat` must be specified.

---

## Keeping your fork in sync with the template

When the upstream template gets improvements you'd like to pull in, add it
as a `template` remote and merge selectively:

```bash
git remote add template https://github.com/SashaBusinaro/ha-hacs-template.git
git fetch template
git merge template/main --no-ff --allow-unrelated-histories
```

---

## License

MIT — see [LICENSE](LICENSE).
