/*
       ____   ____  __ __ ___   ______       _____ ______
      / __ ) / __ \/ //_//   | /_  __/      / ___// ____/
     / __  |/ / / / ,<  / /| |  / /         \__ \/ __/   
    / /_/ // /_/ / /| |/ ___ | / /         ___/ / /___   
   /_____/ \____/_/ |_/_/  |_|/_/         /____/_____/   
                                                     
    Copyright (c) 2025
*/

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

        const activities = state.attributes.activities || [];
        const activityName = state.attributes.activity_name || state.state;
        const activityStatus = state.attributes.activity_status || 'Unknown';
        const activityUrl = state.attributes.activity_url || '';

        this.innerHTML = `
            <ha-card header="${this._config.title || 'Bokat.se'}">
                <div class="card-content">
                    <div class="current-activity">
                        <h2>${activityName}</h2>
                        <p>${activityStatus}</p>
                        <a href="${activityUrl}" target="_blank" class="open-link">Open in Bokat.se</a>
                    </div>
                    
                    ${activities.length > 0 ? `
                        <div class="activity-list">
                            <h3>All Activities</h3>
                            <ul>
                                ${activities.map(activity => `
                                    <li class="${activity.url === activityUrl ? 'selected' : ''}">
                                        <div class="activity-info">
                                            <span class="activity-name">${activity.name}</span>
                                            <span class="activity-status">${activity.status || ''}</span>
                                        </div>
                                        <button class="select-button" data-url="${activity.url}">Select</button>
                                    </li>
                                `).join('')}
                            </ul>
                        </div>
                    ` : ''}
                </div>
                <div class="card-actions">
                    <mwc-button @click="${this._handleRefresh}">Refresh</mwc-button>
                </div>
            </ha-card>
        `;

        // Add event listeners to the select buttons
        const buttons = this.querySelectorAll('.select-button');
        buttons.forEach(button => {
            button.addEventListener('click', () => {
                const url = button.getAttribute('data-url');
                this._handleSelectActivity(url);
            });
        });

        // Add styles
        this.style.cssText = `
            .card-content {
                padding: 16px;
            }
            .current-activity {
                margin-bottom: 24px;
                padding-bottom: 16px;
                border-bottom: 1px solid var(--divider-color, #e0e0e0);
            }
            .current-activity h2 {
                margin: 0 0 8px 0;
                font-size: 1.2em;
                color: var(--primary-text-color);
            }
            .current-activity p {
                margin: 0 0 16px 0;
                color: var(--secondary-text-color);
            }
            .open-link {
                color: var(--primary-color);
                text-decoration: none;
            }
            .activity-list h3 {
                margin: 0 0 16px 0;
                font-size: 1em;
                color: var(--primary-text-color);
            }
            .activity-list ul {
                list-style: none;
                padding: 0;
                margin: 0;
            }
            .activity-list li {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 8px 0;
                border-bottom: 1px solid var(--divider-color, #e0e0e0);
            }
            .activity-list li.selected {
                background-color: var(--primary-color-light, rgba(var(--rgb-primary-color), 0.2));
                border-radius: 4px;
                padding: 8px;
                margin: 0 -8px;
            }
            .activity-info {
                flex: 1;
                overflow: hidden;
            }
            .activity-name {
                display: block;
                font-weight: 500;
                margin-bottom: 4px;
                color: var(--primary-text-color);
            }
            .activity-status {
                display: block;
                font-size: 0.9em;
                color: var(--secondary-text-color);
            }
            .select-button {
                background-color: var(--primary-color);
                color: var(--text-primary-color);
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                cursor: pointer;
                font-size: 0.9em;
            }
            .card-actions {
                border-top: 1px solid var(--divider-color, #e0e0e0);
                padding: 8px 16px;
            }
        `;
    }

    _handleRefresh() {
        if (!this._hass || !this._config) {
            return;
        }

        this._hass.callService('bokat_se', 'refresh', {
            entity_id: this._config.entity
        });
    }

    _handleSelectActivity(url) {
        if (!this._hass || !this._config) {
            return;
        }

        this._hass.callService('bokat_se', 'select_activity', {
            entity_id: this._config.entity,
            activity_url: url
        });
    }

    static getConfigElement() {
        return document.createElement('bokat-se-editor');
    }

    static getStubConfig() {
        return {
            entity: '',
            title: 'Bokat.se'
        };
    }
}

class BokatSeEditor extends HTMLElement {
    constructor() {
        super();
        this._config = {};
        this._hass = null;
    }

    setConfig(config) {
        this._config = config || {
            entity: '',
            title: 'Bokat.se'
        };
    }

    set hass(hass) {
        this._hass = hass;
        this.render();
    }

    render() {
        if (!this._hass) {
            return;
        }

        // Get all sensor entities from Bokat.se integration
        const entities = Object.keys(this._hass.states)
            .filter(entityId => entityId.startsWith('sensor.bokat_se_'))
            .map(entityId => ({
                value: entityId,
                label: this._hass.states[entityId].attributes.friendly_name || entityId
            }));

        this.innerHTML = `
            <div class="editor">
                <ha-form
                    .hass=${this._hass}
                    .data=${this._config}
                    .schema=${[
                        {
                            name: 'entity',
                            selector: {
                                entity: {
                                    domain: 'sensor',
                                    filter: entities.map(e => e.value)
                                }
                            }
                        },
                        {
                            name: 'title',
                            selector: {
                                text: {}
                            }
                        }
                    ]}
                    .computeLabel=${(schema) => schema.name === 'entity' ? 'Entity' : 'Title'}
                    @value-changed=${this._valueChanged}
                ></ha-form>
            </div>
        `;
    }

    _valueChanged(ev) {
        if (!this._config || !this.dispatchEvent) {
            return;
        }

        const newConfig = {
            ...this._config,
            ...ev.detail.value
        };

        this.dispatchEvent(
            new CustomEvent('config-changed', {
                detail: { config: newConfig },
                bubbles: true,
                composed: true
            })
        );
    }
}

customElements.define('bokat-se-card', BokatSeCard);
customElements.define('bokat-se-editor', BokatSeEditor);

window.customCards = window.customCards || [];
window.customCards.push({
    type: 'bokat-se-card',
    name: 'Bokat.se Card',
    description: 'A card to display and interact with Bokat.se activities'
});

console.info(
    '%c BOKAT-SE-CARD %c 1.0.0 ',
    'color: white; background: #3498db; font-weight: 700;',
    'color: #3498db; background: white; font-weight: 700;'
); 