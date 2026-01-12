/**
 * Main application JavaScript
 * Handles loading overlays, SSE connections, and heavy action indicators
 */

(function() {
    'use strict';

    // Loading Overlay Management
    const LoadingOverlay = {
        overlay: null,
        spinner: null,
        text: null,

        init: function() {
            // Create overlay if it doesn't exist
            if (!document.getElementById('loading-overlay')) {
                const overlay = document.createElement('div');
                overlay.id = 'loading-overlay';
                overlay.className = 'loading-overlay';
                overlay.innerHTML = `
                    <div class="loading-spinner">
                        <div class="spinner-border"></div>
                        <div class="loading-text">Processing...</div>
                    </div>
                `;
                document.body.appendChild(overlay);
            }
            this.overlay = document.getElementById('loading-overlay');
        },

        show: function(text) {
            if (!this.overlay) this.init();
            if (text && this.overlay.querySelector('.loading-text')) {
                this.overlay.querySelector('.loading-text').textContent = text;
            }
            this.overlay.classList.add('active');
        },

        hide: function() {
            if (this.overlay) {
                this.overlay.classList.remove('active');
            }
        }
    };

    // Button Spinner Management
    const ButtonSpinner = {
        add: function(button) {
            if (!button.querySelector('.btn-spinner')) {
                const spinner = document.createElement('span');
                spinner.className = 'btn-spinner';
                button.insertBefore(spinner, button.firstChild);
            }
            button.disabled = true;
        },

        remove: function(button) {
            const spinner = button.querySelector('.btn-spinner');
            if (spinner) {
                spinner.remove();
            }
            button.disabled = false;
        }
    };

    // Heavy Action Handler
    const HeavyActions = {
        init: function() {
            // Handle forms with js-heavy-action class
            document.querySelectorAll('form.js-heavy-action').forEach(form => {
                form.addEventListener('submit', function(e) {
                    const submitButton = form.querySelector('button[type="submit"]') || 
                                       form.querySelector('input[type="submit"]');
                    if (submitButton) {
                        ButtonSpinner.add(submitButton);
                    }
                    LoadingOverlay.show('Processing...');
                });
            });

            // Handle sync button specifically
            const syncForm = document.querySelector('form[action="/sync"]');
            if (syncForm) {
                syncForm.addEventListener('submit', function(e) {
                    const button = syncForm.querySelector('button[type="submit"]');
                    if (button) {
                        ButtonSpinner.add(button);
                    }
                    LoadingOverlay.show('Syncing emails...');
                });
            }

            // Handle bulk action buttons
            document.querySelectorAll('button[name="action"]').forEach(button => {
                button.addEventListener('click', function(e) {
                    const form = button.closest('form');
                    if (form && !form.classList.contains('js-heavy-action')) {
                        form.classList.add('js-heavy-action');
                    }
                    const actionText = {
                        'delete': 'Deleting emails...',
                        'unsubscribe': 'Processing unsubscribe...',
                        'assign': 'Assigning category...'
                    }[button.value] || 'Processing...';
                    LoadingOverlay.show(actionText);
                });
            });
        }
    };

    // Server-Sent Events Client
    const SSEClient = {
        eventSource: null,
        reconnectDelay: 3000,
        maxReconnectDelay: 30000,

        init: function() {
            // Only connect on dashboard page
            if (window.location.pathname === '/' || window.location.pathname === '') {
                this.connect();
            }
        },

        connect: function() {
            if (typeof EventSource === 'undefined') {
                console.warn('EventSource not supported, skipping SSE connection');
                return;
            }

            try {
                this.eventSource = new EventSource('/events');
                
                this.eventSource.onopen = () => {
                    console.log('SSE connection opened');
                };

                this.eventSource.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        this.handleEvent(data);
                    } catch (e) {
                        console.error('Failed to parse SSE message:', e);
                    }
                };

                this.eventSource.onerror = (error) => {
                    console.error('SSE connection error:', error);
                    this.eventSource.close();
                    // Reconnect after delay
                    setTimeout(() => {
                        if (window.location.pathname === '/' || window.location.pathname === '') {
                            this.connect();
                        }
                    }, this.reconnectDelay);
                };
            } catch (e) {
                console.error('Failed to create SSE connection:', e);
            }
        },

        handleEvent: function(data) {
            if (data.type === 'connected') {
                console.log('SSE connected');
                return;
            }

            if (data.type === 'email_processed') {
                const count = data.data.added_count || 0;
                if (count > 0) {
                    // Show toast notification
                    if (typeof toastr !== 'undefined') {
                        toastr.success(
                            `${count} new email${count > 1 ? 's' : ''} processed and categorized`,
                            'New Email Processed',
                            { timeOut: 5000 }
                        );
                    }

                    // Update counts - reload page once
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                }
            }
        },

        disconnect: function() {
            if (this.eventSource) {
                this.eventSource.close();
                this.eventSource = null;
            }
        }
    };

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            LoadingOverlay.init();
            HeavyActions.init();
            SSEClient.init();
        });
    } else {
        LoadingOverlay.init();
        HeavyActions.init();
        SSEClient.init();
    }

    // Hide overlay on page load (in case of redirect/refresh)
    window.addEventListener('load', function() {
        LoadingOverlay.hide();
    });

    // Disconnect SSE when leaving dashboard
    window.addEventListener('beforeunload', function() {
        SSEClient.disconnect();
    });

})();

