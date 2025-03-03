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
        this.attachShadow({ mode: 'open' });
    }

    setConfig(config) {
        if (!config.entity) {
            throw new Error('You need to define an entity');
        }
        this._config = {
            show_badges: true,
            show_summary: true,
            enable_response: false,
            title: '',
            ...config
        };
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
                <span class="name">${participant.name}${participant.guests ? ` +${participant.guests}` : ''}</span>
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
            this.shadowRoot.innerHTML = `
                <ha-card>
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

        this.shadowRoot.innerHTML = `
            <style>
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
                    --light-grey-color: var(--light-grey-color, #9e9e9e);
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
                }
                
                .card-header .name {
                    font-size: 1.4em;
                    font-weight: 500;
                    color: var(--text-primary-color);
                }

                .card-header .stats {
                    display: flex;
                    gap: 8px;
                }

                .card-header .stat {
                    display: flex;
                    align-items: center;
                    gap: 4px;
                    color: var(--text-primary-color);
                }
                
                .card-content {
                    padding: 0 0 16px 0;
                }
                
                .participants-section {
                    display: flex;
                    flex-direction: column;
                }
                
                .participant-row {
                    display: grid;
                    grid-template-columns: 20px 1fr auto;
                    grid-template-rows: auto auto;
                    padding: 2px 16px;
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
                    padding-top: 0;
                    padding-left: 0;
                    color: var(--mdc-theme-text-secondary-on-background, rgba(0, 0, 0, .54));
                    font-size: var(--mdc-typography-body2-font-size, .875rem);
                    font-style: italic;
                }

                .stat {
                    position: relative;
                    --ha-ripple-color: var(--badge-color);
                    --ha-ripple-hover-opacity: 0.04;
                    --ha-ripple-pressed-opacity: 0.12;
                    transition: box-shadow 180ms ease-in-out, border-color 180ms ease-in-out;
                    display: flex;
                    flex-direction: row;
                    align-items: center;
                    justify-content: center;
                    gap: 4px;
                    height: var(--ha-badge-size, 24px);
                    min-width: var(--ha-badge-size, 24px);
                    padding: 0 8px;
                    box-sizing: border-box;
                    width: auto;
                    border-radius: var(--ha-badge-border-radius, calc(var(--ha-badge-size, 24px) / 2));
                    background: var(--primary-background-color);
                    border-width: var(--ha-card-border-width, 1px);
                    border-style: solid;
                    border-color: var(--light-grey-color, #9e9e9e);
                    color: var(--primary-text-color);
                    font-size: 1rem;
                }

                .stat ha-icon {
                    --mdc-icon-size: 16px;
                }

                .stat.attending ha-icon {
                    color: var(--success-color, #4caf50);
                }

                .stat.not-attending ha-icon {
                    color: var(--error-color, #f44336);
                }

                .stat.noreply ha-icon {
                    color: var(--light-grey-color, #9e9e9e);
                }

                .response-form {
                    padding: 16px;
                    border-top: 1px solid var(--divider-color);
                    display: flex;
                    flex-direction: column;
                    gap: 16px;
                }

                .response-form .buttons {
                    display: flex;
                    gap: 8px;
                }

                .response-form ha-button {
                    flex: 1;
                    --ha-button-background-color: var(--primary-background-color);
                    --ha-button-text-color: var(--primary-text-color);
                    --ha-button-border-color: var(--divider-color);
                    --ha-button-icon-color: var(--primary-text-color);
                }

                .response-form ha-button.success {
                    --ha-button-background-color: var(--success-color);
                    --ha-button-text-color: white;
                    --ha-button-border-color: var(--success-color);
                    --ha-button-icon-color: white;
                }

                .response-form ha-button.warning {
                    --ha-button-background-color: var(--error-color);
                    --ha-button-text-color: white;
                    --ha-button-border-color: var(--error-color);
                    --ha-button-icon-color: white;
                }

                .response-form .inputs {
                    display: flex;
                    gap: 8px;
                }

                .response-form .comment-field {
                    flex: 1;
                }

                .response-form .guests-field {
                    width: 80px;
                }
            </style>
            <ha-card>
                <div class="card-header">
                    <div class="name">${cardTitle}</div>
                    ${this._config.show_badges ? `
                        <div class="stats">
                            <span class="stat attending">
                                <ha-icon icon="mdi:account-check"></ha-icon>
                                ${totalAttending}
                            </span>
                            <span class="stat not-attending">
                                <ha-icon icon="mdi:account-cancel"></ha-icon>
                                ${notAttendingParticipants.length}
                            </span>
                            <span class="stat noreply">
                                <ha-icon icon="mdi:account-question"></ha-icon>
                                ${noReplyParticipants.length}
                            </span>
                        </div>
                    ` : ''}
                </div>
                ${this._config.show_summary ? `
                    <div class="card-content">
                        <div class="participants-section">
                            ${[...attendingParticipants, ...notAttendingParticipants, ...noReplyParticipants]
                                .map(p => this._renderParticipant(p))
                                .join('')}
                        </div>
                    </div>
                ` : ''}
                ${this._config.enable_response ? `
                    <div class="response-form">
                        <div class="buttons">
                            <ha-button 
                                id="attending-btn"
                                class="success"
                                @click=${this._handleAttending}
                            >
                                <ha-icon icon="mdi:account-check" slot="icon"></ha-icon>
                                Attending
                            </ha-button>
                            <ha-button 
                                id="not-attending-btn"
                                class="warning"
                                @click=${this._handleNotAttending}
                            >
                                <ha-icon icon="mdi:account-cancel" slot="icon"></ha-icon>
                                Not Attending
                            </ha-button>
                        </div>
                        <div class="inputs">
                            <ha-textfield class="comment-field" label="Comment" id="comment"></ha-textfield>
                            <ha-textfield class="guests-field" type="number" min="0" label="Guests" id="guests"></ha-textfield>
                        </div>
                    </div>
                ` : ''}
            </ha-card>
        `;
    }

    _handleAttending() {
        this._handleAttendanceChange('yes');
    }

    _handleNotAttending() {
        this._handleAttendanceChange('no');
    }

    _handleAttendanceChange(attendance) {
        const comment = this.shadowRoot.querySelector('#comment')?.value || '';
        const guests = parseInt(this.shadowRoot.querySelector('#guests')?.value || '0', 10);
        
        this._hass.callService('bokat_se', 'respond', {
            entity_id: this._config.entity,
            attendance: attendance,
            comment,
            guests: attendance === 'yes' ? guests : 0
        });
    }
    
    // This is needed to register the editor with the card
    static getConfigElement() {
        return document.createElement('bokat-se-editor');
    }
    
    // This is needed to provide default config
    static getStubConfig() {
        return { 
            entity: '',
            title: '',
            show_badges: true,
            show_summary: true,
            enable_response: false
        };
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
        this.config = { 
            entity: '',
            title: '',
            show_badges: true,
            show_summary: true,
            enable_response: false
        };
    }

    setConfig(config) {
        this.config = {
            show_badges: true,
            show_summary: true,
            enable_response: false,
            title: '',
            ...config
        };
    }

    get _schema() {
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
                label: this.hass.localize('ui.panel.lovelace.editor.card.generic.title') || 'Title (Optional)',
                selector: { text: {} }
            },
            { 
                name: 'show_badges', 
                label: this.hass.localize('ui.panel.lovelace.editor.card.bokat-se.show_badges') || 'Show status badges',
                selector: { boolean: {} }
            },
            { 
                name: 'show_summary', 
                label: this.hass.localize('ui.panel.lovelace.editor.card.bokat-se.show_summary') || 'Show participant list',
                selector: { boolean: {} }
            },
            { 
                name: 'enable_response', 
                label: this.hass.localize('ui.panel.lovelace.editor.card.bokat-se.enable_response') || 'Enable response form',
                selector: { boolean: {} }
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
        const config = ev.detail.value;
        this.dispatchEvent(new CustomEvent('config-changed', { detail: { config } }));
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

