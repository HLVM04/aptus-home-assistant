# Aptus Home Assistant Integration

A Home Assistant custom integration for interfacing with Aptus home entrance locks. This integration allows you to control your Aptus Home lock system directly from Home Assistant.

## Features

- Unlock entrance doors from Aptus Home
- Integrate with Home Assitant automations

## Roadmap

- Locked state monitoring
- HA event on entrance door buzz
- Camera support
- Support for non-entrance door locks

## Installation

### HACS (Recommended)
1. Open HACS in your Home Assistant instance
2. Go to "Integrations"
3. Click the three dots in the top right corner and select "Custom repositories"
4. Add this repository URL and select "Integration" as the category
5. Install the Aptus integration
6. Restart Home Assistant

### Manual Installation
1. Download the latest release from the releases page
2. Extract the contents to your `custom_components/aptus_home` directory
3. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "Aptus Home"
4. Follow the configuration flow to set up your Aptus Home connection

> IMPORTANT: Make sure the host parameter is correctly formated. Example: https://DOMAIN.aptustotal.se/AptusPortal/

## Development

1. Open this repository in Visual Studio Code with the Dev Containers extension
2. Use the "`Dev Containers: Clone Repository in Named Container Volume...`" option
3. Run the `scripts/develop` script to start Home Assistant and test the integration

## Support

If you encounter any issues or have questions:
1. Check the [Issues](../../issues) page for existing problems and solutions
2. Create a new issue if your problem isn't already reported
3. Provide detailed information about your Aptus Home configuration and Home Assistant setup
