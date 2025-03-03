/*
       ____   ____  __ __ ___   ______       _____ ______
      / __ ) / __ \/ //_//   | /_  __/      / ___// ____/
     / __  |/ / / / ,<  / /| |  / /         \__ \/ __/   
    / /_/ // /_/ / /| |/ ___ | / /         ___/ / /___   
   /_____/ \____/_/ |_/_/  |_|/_/         /____/_____/   
                                                     
    Copyright (c) 2025
*/

// This version should match the VERSION in const.py
const CARD_VERSION = "1.0.0";

class BokatSeCard extends HTMLElement {
    constructor() {
        super();
        this._config = {};
        this._hass = null;
    }

    setConfig(config) {
        if (!config.entity) {
            throw new Error('You need to define an entity');
        }
        this._config = config;
    }

    set hass(hass) {
        this._hass = hass;
        this.render();
    }

    getCardSize() {
        return 3;
    }

    // Format status for display
    _formatStatus(status) {
        switch(status) {
            case 'Attending':
                return 'Attending';
            case 'NotAttending':
                return 'Not Attending';
            case 'NoReply':
                return 'No Reply';
            default:
                return status;
        }
    }

    // Filter participants by status
    _filterParticipants(participants, status) {
        return participants.filter(p => p.status === status);
    }

    render() {
        if (!this._hass || !this._config) {
            return;
        }

        const entityId = this._config.entity;
        const state = this._hass.states[entityId];

        if (!state) {
            this.innerHTML = `
                <ha-card header="Bokat.se">
                    <div class="card-content">
                        Entity not found: ${entityId}
                    </div>
                </ha-card>
            `;
            return;
        }

        // Get data from the sensor entity attributes
        const activityName = state.attributes.activity_name || state.attributes.friendly_name || entityId;
        
        // Use title from config if available, otherwise use activity name
        const cardTitle = this._config.title || activityName;
        
        // Participant information
        const participants = state.attributes.participants || [];
        
        // Get the total attending count from the entity state
        const totalAttending = state.state || 0;
        
        // Filter participants by status
        const attendingParticipants = this._filterParticipants(participants, 'Attending');
        const notAttendingParticipants = this._filterParticipants(participants, 'NotAttending');
        const noReplyParticipants = this._filterParticipants(participants, 'NoReply');
        
        // Calculate counts from the filtered arrays
        const notAttendingCount = notAttendingParticipants.length;
        const noResponseCount = noReplyParticipants.length;
        const guestsCount = participants.reduce((sum, p) => sum + (p.guests || 0), 0);

        this.innerHTML = `
            <ha-card>
                <div class="card-header">
                    <div class="name">${cardTitle}</div>
                </div>
                <div class="card-content">
                    <div class="summary">
                        <h3>Totalt antal spelare ${totalAttending}</h3>
                        <p>
                            <em>Kommer inte:</em> ${notAttendingCount}<br>
                            <em>Inget svar:</em> ${noResponseCount}<br>
                            <em>Gäster:</em> ${guestsCount}
                        </p>
                    </div>
                    
                    <div class="participants-section">
                        <h4>Spelare:</h4>
                        <ul class="participants-list">
                            ${attendingParticipants.map(p => `
                                <li>
                                    <em>${p.name}${p.guests ? ` +${p.guests}` : ''}${p.comment ? ` (${p.comment})` : ''}</em>
                                </li>
                            `).join('')}
                        </ul>
                        
                        <h4>Tackat nej:</h4>
                        <ul class="participants-list">
                            ${notAttendingParticipants.map(p => `
                                <li>
                                    <em>${p.name}${p.guests ? ` +${p.guests}` : ''}${p.comment ? ` (${p.comment})` : ''}</em>
                                </li>
                            `).join('')}
                        </ul>
                        
                        <h4>Ej svarat:</h4>
                        <ul class="participants-list">
                            ${noReplyParticipants.map(p => `
                                <li>
                                    <em>${p.name}${p.guests ? ` +${p.guests}` : ''}${p.comment ? ` (${p.comment})` : ''}</em>
                                </li>
                            `).join('')}
                        </ul>
                    </div>
                </div>
            </ha-card>
        `;

        // Add styles
        this.style.cssText = `
            :host {
                --primary-color: var(--primary-color, #03a9f4);
                --secondary-color: var(--secondary-color, #607d8b);
                --text-primary-color: var(--primary-text-color, #212121);
                --text-secondary-color: var(--secondary-text-color, #727272);
                --divider-color: var(--divider-color, #e0e0e0);
                --background-color: var(--card-background-color, white);
                --success-color: var(--success-color, #4caf50);
                --error-color: var(--error-color, #f44336);
                --warning-color: var(--warning-color, #ff9800);
            }
            
            ha-card {
                padding: 0;
                overflow: hidden;
            }
            
            .card-header {
                padding: 16px 16px 0;
            }
            
            .card-header .name {
                font-size: 1.4em;
                font-weight: 500;
                color: var(--text-primary-color);
            }
            
            .card-content {
                padding: 16px;
            }
            
            .summary h3 {
                margin: 0 0 8px 0;
                font-size: 1.1em;
                font-weight: 500;
            }
            
            .summary p {
                margin: 0 0 16px 0;
                line-height: 1.5;
            }
            
            .participants-section h4 {
                margin: 16px 0 8px 0;
                font-size: 1em;
                font-weight: 500;
                border-bottom: 1px solid var(--divider-color);
                padding-bottom: 4px;
            }
            
            .participants-list {
                list-style-type: none;
                padding: 0;
                margin: 0;
            }
            
            .participants-list li {
                padding: 4px 0;
            }
            
            em {
                font-style: italic;
                font-weight: normal;
            }
        `;
    }
    
    // This is needed to register the editor with the card
    static getConfigElement() {
        return document.createElement('bokat-se-editor');
    }
    
    // This is needed to provide default config
    static getStubConfig() {
        return { entity: '' };
    }
}

// Import LitElement for the editor
import { LitElement, html, css } from 'https://unpkg.com/lit@2.7.6/index.js?module';

class BokatSeEditor extends LitElement {
    static get properties() {
        return {
            hass: { type: Object },
            config: { type: Object }
        };
    }

    constructor() {
        super();
        this.config = { entity: '' };
    }

    setConfig(config) {
        this.config = { ...config };
    }

    static get styles() {
        return css`
            .editor {
                padding: 8px;
            }
        `;
    }

    get _schema() {
        // Get all sensor entities that start with 'sensor.bokat_se'
        const entities = Object.keys(this.hass.states)
            .filter(entityId => entityId.startsWith('sensor.bokat_se'))
            .sort();

        return [
            { 
                name: 'entity', 
                label: this.hass.localize('ui.panel.lovelace.editor.card.generic.entity') || 'Entity', 
                selector: { 
                    entity: { 
                        domain: 'sensor',
                        integration: 'bokat_se'
                    } 
                } 
            },
            { 
                name: 'title', 
                label: this.hass.localize('ui.panel.lovelace.editor.card.generic.title') || 'Title', 
                selector: { text: {} } 
            }
        ];
    }

    render() {
        if (!this.hass) {
            return html`<div>Loading...</div>`;
        }

        return html`
            <div class="editor">
                <ha-form
                    .hass=${this.hass}
                    .data=${this.config}
                    .schema=${this._schema}
                    @value-changed=${this._valueChanged}
                ></ha-form>
            </div>
        `;
    }

    _valueChanged(ev) {
        if (!this.config) {
            return;
        }

        const newConfig = { ...this.config, ...ev.detail.value };
        
        // Dispatch the config-changed event
        const event = new CustomEvent('config-changed', {
            detail: { config: newConfig },
            bubbles: true,
            composed: true,
        });
        this.dispatchEvent(event);
        this.config = newConfig;
    }
}

customElements.define('bokat-se-card', BokatSeCard);
customElements.define('bokat-se-editor', BokatSeEditor);

// Register the card with Home Assistant
window.customCards = window.customCards || [];
window.customCards.push({
    type: 'bokat-se-card',
    name: 'Bokat.se Card',
    description: 'A card to display and interact with Bokat.se activities',
    preview: false,
    configurable: true
});

console.info(
    '%c BOKAT-SE-CARD %c ' + CARD_VERSION + ' ',
    'color: white; background: #3498db; font-weight: 700;',
    'color: #3498db; background: white; font-weight: 700;'
);
