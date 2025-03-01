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
        
        // Participant information
        const participants = state.attributes.participants || [];
        const totalParticipants = state.attributes.total_participants || 0;
        const attendingCount = state.attributes.attending_count || 0;
        const notAttendingCount = state.attributes.not_attending_count || 0;
        const noResponseCount = state.attributes.no_response_count || 0;
        const answerUrl = state.attributes.answer_url || '';

        this.innerHTML = `
            <ha-card header="${this._config.title || 'Bokat.se'}">
                <div class="card-content">
                    <div class="current-activity">
                        <h2>${activityName}</h2>
                        <p>${activityStatus}</p>
                        <a href="${activityUrl}" target="_blank" class="open-link">Open in Bokat.se</a>
                    </div>
                    
                    ${participants.length > 0 ? `
                        <div class="participant-summary">
                            <h3>Participants</h3>
                            <div class="participant-stats">
                                <div class="stat">
                                    <span class="stat-value">${totalParticipants}</span>
                                    <span class="stat-label">Total</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-value">${attendingCount}</span>
                                    <span class="stat-label">Attending</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-value">${notAttendingCount}</span>
                                    <span class="stat-label">Not Attending</span>
                                </div>
                                <div class="stat">
                                    <span class="stat-value">${noResponseCount}</span>
                                    <span class="stat-label">No Response</span>
                                </div>
                            </div>
                            
                            <div class="participant-list">
                                <details>
                                    <summary>Show Participants</summary>
                                    <table>
                                        <thead>
                                            <tr>
                                                <th>Name</th>
                                                <th>Status</th>
                                                <th>Comment</th>
                                                <th>Time</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            ${participants.map(participant => `
                                                <tr class="participant-row ${participant.status}">
                                                    <td>${participant.name}</td>
                                                    <td>${this._formatStatus(participant.status)}</td>
                                                    <td>${participant.comment || ''}</td>
                                                    <td>${participant.timestamp || ''}</td>
                                                </tr>
                                            `).join('')}
                                        </tbody>
                                    </table>
                                </details>
                            </div>
                            
                            ${answerUrl ? `
                                <div class="response-form">
                                    <h3>Respond</h3>
                                    <div class="form-row">
                                        <label for="attendance">Attendance:</label>
                                        <select id="attendance" class="attendance-select">
                                            <option value="yes">Attending</option>
                                            <option value="no">Not Attending</option>
                                            <option value="comment_only">Comment Only</option>
                                        </select>
                                    </div>
                                    <div class="form-row guests-row">
                                        <label for="guests">Guests:</label>
                                        <input type="number" id="guests" class="guests-input" min="0" value="0">
                                    </div>
                                    <div class="form-row">
                                        <label for="comment">Comment:</label>
                                        <textarea id="comment" class="comment-input" rows="2"></textarea>
                                    </div>
                                    <button class="submit-button">Submit Response</button>
                                </div>
                            ` : ''}
                        </div>
                    ` : ''}
                    
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
        
        // Add event listener to the submit response button
        const submitButton = this.querySelector('.submit-button');
        if (submitButton) {
            submitButton.addEventListener('click', () => {
                this._handleSubmitResponse();
            });
        }
        
        // Add event listener to the attendance select to show/hide guests input
        const attendanceSelect = this.querySelector('.attendance-select');
        if (attendanceSelect) {
            attendanceSelect.addEventListener('change', () => {
                const guestsRow = this.querySelector('.guests-row');
                if (guestsRow) {
                    guestsRow.style.display = attendanceSelect.value === 'yes' ? 'flex' : 'none';
                }
            });
            // Trigger the change event to set initial state
            attendanceSelect.dispatchEvent(new Event('change'));
        }

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
            
            /* Participant styles */
            .participant-summary {
                margin-bottom: 24px;
                padding-bottom: 16px;
                border-bottom: 1px solid var(--divider-color, #e0e0e0);
            }
            .participant-summary h3 {
                margin: 0 0 16px 0;
                font-size: 1em;
                color: var(--primary-text-color);
            }
            .participant-stats {
                display: flex;
                justify-content: space-between;
                margin-bottom: 16px;
            }
            .stat {
                text-align: center;
                flex: 1;
            }
            .stat-value {
                display: block;
                font-size: 1.5em;
                font-weight: bold;
                color: var(--primary-text-color);
            }
            .stat-label {
                display: block;
                font-size: 0.8em;
                color: var(--secondary-text-color);
            }
            .participant-list {
                margin-bottom: 16px;
            }
            .participant-list details {
                margin-bottom: 16px;
            }
            .participant-list summary {
                cursor: pointer;
                color: var(--primary-color);
                font-weight: 500;
                margin-bottom: 8px;
            }
            .participant-list table {
                width: 100%;
                border-collapse: collapse;
                font-size: 0.9em;
            }
            .participant-list th {
                text-align: left;
                padding: 8px 4px;
                border-bottom: 1px solid var(--divider-color, #e0e0e0);
                color: var(--primary-text-color);
            }
            .participant-list td {
                padding: 8px 4px;
                border-bottom: 1px solid var(--divider-color, #e0e0e0);
                color: var(--secondary-text-color);
            }
            .participant-row.attending td:nth-child(2) {
                color: var(--success-color, green);
            }
            .participant-row.not_attending td:nth-child(2) {
                color: var(--error-color, red);
            }
            .participant-row.no_response td:nth-child(2) {
                color: var(--warning-color, orange);
            }
            
            /* Response form styles */
            .response-form {
                margin-top: 16px;
                padding: 16px;
                background-color: var(--card-background-color, #fff);
                border-radius: 4px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }
            .response-form h3 {
                margin: 0 0 16px 0;
                font-size: 1em;
                color: var(--primary-text-color);
            }
            .form-row {
                display: flex;
                flex-direction: column;
                margin-bottom: 12px;
            }
            .form-row label {
                margin-bottom: 4px;
                font-size: 0.9em;
                color: var(--primary-text-color);
            }
            .attendance-select, .guests-input, .comment-input {
                padding: 8px;
                border: 1px solid var(--divider-color, #e0e0e0);
                border-radius: 4px;
                background-color: var(--card-background-color, #fff);
                color: var(--primary-text-color);
            }
            .submit-button {
                background-color: var(--primary-color);
                color: var(--text-primary-color);
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                cursor: pointer;
                font-size: 1em;
                width: 100%;
                margin-top: 8px;
            }
            
            /* Activity list styles */
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

    _formatStatus(status) {
        switch (status) {
            case 'attending':
                return 'Attending';
            case 'not_attending':
                return 'Not Attending';
            case 'no_response':
                return 'No Response';
            default:
                return 'Unknown';
        }
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
    
    _handleSubmitResponse() {
        if (!this._hass || !this._config) {
            return;
        }
        
        const attendanceSelect = this.querySelector('.attendance-select');
        const guestsInput = this.querySelector('.guests-input');
        const commentInput = this.querySelector('.comment-input');
        
        if (!attendanceSelect) {
            return;
        }
        
        const attendance = attendanceSelect.value;
        const guests = guestsInput ? parseInt(guestsInput.value, 10) || 0 : 0;
        const comment = commentInput ? commentInput.value : '';
        
        this._hass.callService('bokat_se', 'respond', {
            entity_id: this._config.entity,
            attendance: attendance,
            guests: guests,
            comment: comment
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
    '%c BOKAT-SE-CARD %c 2.0.0 ',
    'color: white; background: #3498db; font-weight: 700;',
    'color: #3498db; background: white; font-weight: 700;'
); 