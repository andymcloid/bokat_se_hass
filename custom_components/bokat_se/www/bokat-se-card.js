/*
       ____   ____  __ __ ___   ______       _____ ______
      / __ ) / __ \/ //_//   | /_  __/      / ___// ____/
     / __  |/ / / / ,<  / /| |  / /         \__ \/ __/   
    / /_/ // /_/ / /| |/ ___ | / /         ___/ / /___   
   /_____/ \____/_/ |_/_/  |_|/_/         /____/_____/   
                                                     
    Copyright (c) 2025
*/

// This version should match the VERSION in const.py
const CARD_VERSION = "2.1.0";

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

    // Get status icon and color
    _getStatusIcon(status, hasComment) {
        if (hasComment && status === 'NoReply') {
            return {
                icon: 'mdi:comment-outline',
                color: 'var(--info-color, #039be5)'
            };
        }
        
        switch(status) {
            case 'Attending':
                return {
                    icon: 'mdi:check-bold',
                    color: 'var(--success-color, #4caf50)'
                };
            case 'NotAttending':
                return {
                    icon: 'mdi:close-thick',
                    color: 'var(--error-color, #f44336)'
                };
            case 'NoReply':
                return {
                    icon: 'mdi:help',
                    color: 'var(--disabled-text-color, #9e9e9e)'
                };
            default:
                return {
                    icon: 'mdi:help',
                    color: 'var(--disabled-text-color, #9e9e9e)'
                };
        }
    }

    // Render participant row
    _renderParticipant(participant) {
        const statusInfo = this._getStatusIcon(participant.status, !!participant.comment);
        return `
            <div class="participant-row">
                <ha-icon
                    icon="${statusInfo.icon}"
                    style="color: ${statusInfo.color};"
                ></ha-icon>
                <span class="name">${participant.name}</span>
                ${participant.guests ? `<span class="guests">+${participant.guests}</span>` : ''}
                ${participant.comment ? `<div class="comment">${participant.comment}</div>` : ''}
            </div>
        `;
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

        const activityName = state.attributes.activity_name || state.attributes.friendly_name || entityId;
        const cardTitle = this._config.title || activityName;
        const participants = state.attributes.participants || [];
        const totalAttending = state.state || 0;
        
        const attendingParticipants = this._filterParticipants(participants, 'Attending');
        const notAttendingParticipants = this._filterParticipants(participants, 'NotAttending');
        const noReplyParticipants = this._filterParticipants(participants, 'NoReply');
        
        const notAttendingCount = notAttendingParticipants.length;
        const noResponseCount = noReplyParticipants.length;
        const guestsCount = participants.reduce((sum, p) => sum + (p.guests || 0), 0);

        this.innerHTML = `
            <ha-card>
                <div class="card-header">
                    <div class="name">${cardTitle}</div>
                    <div class="stats">
                        <span class="stat">
                            <ha-icon icon="mdi:account-group" style="color: var(--primary-color);"></ha-icon>
                            ${totalAttending}
                        </span>
                        <span class="stat">
                            <ha-icon icon="mdi:account-multiple-plus" style="color: var(--info-color);"></ha-icon>
                            ${guestsCount}
                        </span>
                    </div>
                </div>
                <div class="card-content">
                    <div class="participants-section">
                        ${[...attendingParticipants, ...notAttendingParticipants, ...noReplyParticipants]
                            .map(p => this._renderParticipant(p))
                            .join('')}
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
                --text-hint-color: var(--text-hint-color, #909090);
                --divider-color: var(--divider-color, #e0e0e0);
                --background-color: var(--card-background-color, white);
                --success-color: var(--success-color, #4caf50);
                --error-color: var(--error-color, #f44336);
                --warning-color: var(--warning-color, #ff9800);
                --info-color: var(--info-color, #039be5);
                --disabled-text-color: var(--disabled-text-color, #9e9e9e);
                --light-primary-color: var(--light-primary-color, #e1f5fe);
            }
            
            ha-card {
                padding: 0;
                overflow: hidden;
            }
            
            .card-header {
                padding: 16px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                border-bottom: 1px solid var(--divider-color);
            }
            
            .card-header .name {
                font-size: 1.2em;
                font-weight: 500;
                color: var(--text-primary-color);
            }

            .card-header .stats {
                display: flex;
                gap: 16px;
            }

            .card-header .stat {
                display: flex;
                align-items: center;
                gap: 4px;
                color: var(--text-primary-color);
            }
            
            .card-content {
                padding: 0;
            }
            
            .participants-section {
                display: flex;
                flex-direction: column;
            }
            
            .participant-row {
                display: grid;
                grid-template-columns: 20px 1fr auto;
                grid-template-rows: auto auto;
                padding: 8px 16px;
                border-bottom: 1px solid var(--divider-color);
                align-items: center;
                gap: 0 8px;
            }
            
            .participant-row:last-child {
                border-bottom: none;
            }
            
            .participant-row ha-icon {
                grid-row: 1;
                grid-column: 1;
                --mdc-icon-size: 16px;
            }
            
            .participant-row .name {
                grid-row: 1;
                grid-column: 2;
                color: var(--text-primary-color);
                font-weight: normal;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }
            
            .participant-row .guests {
                grid-row: 1;
                grid-column: 3;
                padding: 1px 4px;
                background: var(--info-color);
                color: white;
                border-radius: 12px;
                font-size: 0.8em;
            }
            
            .participant-row .comment {
                grid-row: 2;
                grid-column: 2 / -1;
                color: var(--disabled-text-color);
                font-size: 0.85em;
                line-height: 1.2;
                opacity: 0.5;
                padding-top: 2px;
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

