/*
       ____   ____  __ __ ___   ______       _____ ______
      / __ ) / __ \/ //_//   | /_  __/      / ___// ____/
     / __  |/ / / / ,<  / /| |  / /         \__ \/ __/   
    / /_/ // /_/ / /| |/ ___ | / /         ___/ / /___   
   /_____/ \____/_/ |_/_/  |_|/_/         /____/_____/   
                                                     
    Copyright (c) 2025
*/

// This version should match the VERSION in const.py
const CARD_VERSION = "2.2.0";

class BokatSeCard extends HTMLElement {
    constructor() {
        super();
        this._config = {};
        this._hass = null;
        this._loading = false;
        this._loadingButton = null;
        this._comment = '';
        this._guests = 0;
        this._translations = null;
        this.attachShadow({ mode: 'open' });
        
        // Bind the handlers
        this._handleClick = this._handleClick.bind(this);
        this._handleInput = this._handleInput.bind(this);
    }

    async loadTranslations(language) {
        try {
            const response = await fetch(`/bokat_se/localization/${language}.json`);
            if (response.ok) {
                this._translations = await response.json();
            } else {
                // Fallback to English if language not found
                const fallbackResponse = await fetch('/bokat_se/localization/en.json');
                this._translations = await fallbackResponse.json();
            }
        } catch (error) {
            console.error('Failed to load translations:', error);
            // Set empty translations object as fallback
            this._translations = {};
        }
    }

    translate(key, fallback) {
        return this._translations?.[key] || fallback;
    }

    connectedCallback() {
        if (window.customCards) {
            window.customCards.push({
                type: "bokat-se-card",
                name: "Bokat.se Card",
                preview: false,
            });
        }

        // Force connection to Home Assistant
        if (window.hassConnection) {
            window.hassConnection.then(() => {
                this._initialized = true;
                this.render();
            });
        }

        this.shadowRoot.addEventListener('click', this._handleClick);
        this.shadowRoot.addEventListener('input', this._handleInput);
    }

    disconnectedCallback() {
        this.shadowRoot.removeEventListener('click', this._handleClick);
        this.shadowRoot.removeEventListener('input', this._handleInput);
    }

    set hass(hass) {
        if (!this._initialized && hass) {
            this._initialized = true;
            // Load translations when hass is first set
            this.loadTranslations(hass.locale?.language || 'en');
        }
        this._hass = hass;
        this.render();
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

    getCardSize() {
        return 3;
    }

    // Format status for display
    _formatStatus(status) {
        switch(status) {
            case 'Attending':
                return this.translate('status_attending', 'Attending');
            case 'NotAttending':
                return this.translate('status_not_attending', 'Not Attending');
            case 'NoReply':
                return this.translate('status_no_reply', 'No Reply');
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
            // console.log('Render skipped - missing hass or config');
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

                .response-form button {
                    flex: 1;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 8px;
                    padding: 8px 16px;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 12px;
                    font-weight: 700;
                    letter-spacing: 0.5px;
                    text-transform: uppercase;
                    transition: all 0.2s ease;
                    position: relative;
                    background: var(--primary-color);
                    color: white;
                    text-shadow: 0 1px 1px rgba(0,0,0,0.1);
                }

                .response-form button:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }

                .response-form button.success {
                    background: var(--success-color, #4caf50);
                    color: white;
                }

                .response-form button.warning {
                    background: var(--error-color, #f44336);
                    color: white;
                }

                .response-form button.info {
                    background: var(--info-color, #039be5);
                    color: white;
                }

                .response-form button:hover:not(:disabled) {
                    opacity: 0.9;
                    transform: translateY(-1px);
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }

                .response-form button:active:not(:disabled) {
                    transform: translateY(0);
                    box-shadow: none;
                }

                .response-form .loading-spinner {
                    width: 16px;
                    height: 16px;
                    border: 2px solid rgba(255,255,255,0.3);
                    border-top-color: white;
                    border-radius: 50%;
                    animation: spin 0.6s linear infinite;
                    position: absolute;
                    right: 8px;
                }

                @keyframes spin {
                    to {
                        transform: rotate(360deg);
                    }
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

                ha-icon {
                    --mdc-icon-size: 20px;
                    margin-right: 4px;
                }

                :host {
                    --button-text-color: white;
                }

                :host-context([theme="dark"]) {
                    --button-text-color: white;
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
                            <button 
                                id="attending-btn"
                                class="success"
                                ?disabled="${this._loading}"
                                type="button"
                            >
                                <ha-icon icon="mdi:account-check"></ha-icon>
                                <span>${this.translate('action_attending', 'Attending')}</span>
                                ${this._loadingButton === 'attending-btn' ? '<div class="loading-spinner"></div>' : ''}
                            </button>
                            <button 
                                id="not-attending-btn"
                                class="warning"
                                ?disabled="${this._loading}"
                                type="button"
                            >
                                <ha-icon icon="mdi:account-cancel"></ha-icon>
                                <span>${this.translate('action_not_attending', 'Not Attending')}</span>
                                ${this._loadingButton === 'not-attending-btn' ? '<div class="loading-spinner"></div>' : ''}
                            </button>
                            <button 
                                id="only-comment-btn"
                                class="info"
                                ?disabled="${this._loading}"
                                type="button"
                            >
                                <ha-icon icon="mdi:comment-text-outline"></ha-icon>
                                <span>${this.translate('action_only_comment', 'Only Comment')}</span>
                                ${this._loadingButton === 'only-comment-btn' ? '<div class="loading-spinner"></div>' : ''}
                            </button>
                        </div>
                        <div class="inputs">
                            <ha-textfield 
                                class="comment-field" 
                                label="${this.translate('field_comment', 'Comment')}" 
                                id="comment"
                                .value="${this._comment}"
                                .disabled="${this._loading}"
                            ></ha-textfield>
                            <ha-textfield 
                                class="guests-field" 
                                type="number" 
                                min="0" 
                                label="${this.translate('field_guests', 'Guests')}" 
                                id="guests"
                                .value="${this._guests}"
                                .disabled="${this._loading}"
                            ></ha-textfield>
                        </div>
                    </div>
                ` : ''}
            </ha-card>
        `;
    }

    _updateButtonStates(loading, buttonId = null) {
        this._loading = loading;
        this._loadingButton = loading ? buttonId : null;
        this.render();
    }

    _handleInput(event) {
        const target = event.target;
        if (!target) return;

        if (target.id === 'comment') {
            this._comment = target.value;
        } else if (target.id === 'guests') {
            this._guests = target.value ? parseInt(target.value, 10) : 0;
        }
    }

    async _handleAttendanceChange(attendance, buttonId) {
        if (this._loading) return;
        
        if (!this._hass) {
            console.error('Home Assistant connection not ready');
            return;
        }
        
        try {
            this._loading = true;
            this._updateButtonStates(true, buttonId);

            await this._hass.callService('bokat_se', 'respond', {
                entity_id: this._config.entity,
                attendance,
                comment: this._comment,
                guests: this._guests
            });

            // Clear inputs after successful response
            this._comment = '';
            this._guests = 0;
            this.render();
            
        } catch (error) {
            console.error('Failed to update attendance:', error);
        } finally {
            this._loading = false;
            this._updateButtonStates(false);
        }
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

    // Update styles
    static get styles() {
        return css`
            .buttons {
                display: flex;
                gap: 8px;
            }

            button {
                flex: 1;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 700;
                letter-spacing: 0.5px;
                text-transform: uppercase;
                transition: all 0.2s ease;
                position: relative;
                background: var(--primary-color);
                color: white;
                text-shadow: 0 1px 1px rgba(0,0,0,0.1);
            }

            button:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }

            button.success {
                background: var(--success-color, #4caf50);
                color: white;
            }

            button.warning {
                background: var(--error-color, #f44336);
                color: white;
            }

            button.info {
                background: var(--info-color, #039be5);
                color: white;
            }

            button:hover:not(:disabled) {
                opacity: 0.9;
                transform: translateY(-1px);
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }

            button:active:not(:disabled) {
                transform: translateY(0);
                box-shadow: none;
            }

            ha-icon {
                --mdc-icon-size: 20px;
                margin-right: 4px;
            }

            .loading-spinner {
                width: 16px;
                height: 16px;
                border: 2px solid rgba(255,255,255,0.3);
                border-top-color: white;
                border-radius: 50%;
                animation: spin 0.6s linear infinite;
                position: absolute;
                right: 8px;
            }

            @keyframes spin {
                to {
                    transform: rotate(360deg);
                }
            }

            :host {
                --button-text-color: white;
            }

            :host-context([theme="dark"]) {
                --button-text-color: white;
            }
        `;
    }

    _handleClick(event) {
        const button = event.target.closest('button');
        if (!button) return;

        if (!this._hass || !window.hassConnection) {
            console.error('No Home Assistant connection');
            return;
        }

        switch(button.id) {
            case 'attending-btn':
                this._handleAttendanceChange('yes', button.id);
                break;
            case 'not-attending-btn':
                this._handleAttendanceChange('no', button.id);
                break;
            case 'only-comment-btn':
                this._handleAttendanceChange('comment_only', button.id);
                break;
        }
    }
}

// Import LitElement for the editor
import { LitElement, html, css } from 'https://unpkg.com/lit@2.7.6/index.js?module';

class BokatSeEditor extends LitElement {
    static get properties() {
        return {
            hass: {},
            config: {}
        };
    }

    constructor() {
        super();
        this.config = {};
        this._translations = null;
        this._computeLabel = this._computeLabel.bind(this);
    }

    static get styles() {
        return css`
            ha-form {
                width: 100%;
            }
            
            /* Direct override for ha-formfield */
            ha-formfield {
                min-height: 0 !important;
                padding: 4px 0 !important;
                display: block !important;
            }
            
            /* Target all form elements */
            ::slotted(ha-formfield) {
                min-height: 0 !important;
                padding: 4px 0 !important;
            }
            
            /* Force all checkboxes to be compact */
            ha-checkbox {
                --mdc-checkbox-state-layer-size: 24px !important;
            }
        `;
    }

    _computeLabel(schema) {
        if (schema.label) {
            return schema.label;
        }
        return schema.name;
    }

    async loadTranslations(language) {
        try {
            const response = await fetch(`/bokat_se/localization/${language}.json`);
            if (response.ok) {
                this._translations = await response.json();
                this.requestUpdate();
            } else {
                const fallbackResponse = await fetch('/bokat_se/localization/en.json');
                this._translations = await fallbackResponse.json();
                this.requestUpdate();
            }
        } catch (error) {
            console.error('Failed to load translations:', error);
            this._translations = {};
            this.requestUpdate();
        }
    }

    translate(key, fallback) {
        return this._translations?.[key] || fallback;
    }

    updated(changedProps) {
        if (changedProps.has('hass') && this.hass) {
            this.loadTranslations(this.hass.locale?.language || 'en');
        }
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
        if (!this._translations) {
            return [];
        }

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
                label: this.translate('editor_show_badges', 'Show status badges'),
                selector: { boolean: {} }
            },
            { 
                name: 'show_summary', 
                label: this.translate('editor_show_summary', 'Show participant list'),
                selector: { boolean: {} }
            },
            { 
                name: 'enable_response', 
                label: this.translate('editor_enable_response', 'Enable response form'),
                selector: { boolean: {} }
            }
        ];
    }

    render() {
        if (!this.hass || !this._translations) {
            return html`<div>Loading...</div>`;
        }

        return html`
            <div class="editor">
                <ha-form
                    .hass=${this.hass}
                    .data=${this.config}
                    .schema=${this._schema}
                    .computeLabel=${this._computeLabel}
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


