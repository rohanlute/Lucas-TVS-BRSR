/**
 * BRSR Dynamic Validation System
 * Production-ready client-side validation for JSON-driven forms.
 * All validators are driven by field_type from JSON schema.
 */

(function() {
    'use strict';

    // ============================================================
    // 1. VALIDATOR DEFINITIONS
    // ============================================================

    /**
     * Each validator is an object with:
     *   - test: function(value) => boolean (true = valid)
     *   - message: string or function(fieldName) => string (only used when field is required)
     *   - format: optional function(value) => formatted string
     *   - pattern: optional regex for HTML5 pattern attribute
     *   - inputmode: optional string for HTML5 inputmode
     *   - maxlength: optional number
     */
    const VALIDATORS = {

        alphabetic: {
            test: (v) => /^[A-Za-z\s]+$/.test(v),
            message: (name) => `${name} must contain only letters and spaces.`,
            pattern: '^[A-Za-z\\s]+$',
            inputmode: 'text',
            maxlength: 100,
        },

        alphanumeric: {
            test: (v) => /^[A-Za-z0-9\s]+$/.test(v),
            message: (name) => `${name} must contain only letters, numbers, and spaces.`,
            pattern: '^[A-Za-z0-9\\s]+$',
            inputmode: 'text',
            maxlength: 100,
        },

        phone: {
            test: (v) => /^[0-9]{10,15}$/.test(v),
            message: (name) => `${name} must be a valid 10-15 digit phone number.`,
            pattern: '[0-9]{10,15}',
            inputmode: 'tel',
            maxlength: 15,
            format: (v) => v.replace(/[^0-9]/g, ''),
        },

        telephone: {
            test: (v) => /^[0-9+\-()\s]{8,20}$/.test(v),
            message: (name) => `${name} must be a valid telephone number (8-20 digits, +, -, (), space).`,
            inputmode: 'tel',
            maxlength: 20,
            format: (v) => v.replace(/[^0-9+\-()\s]/g, ''),
        },

        email: {
            test: (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v),
            message: (name) => `${name} must be a valid email address (e.g., name@domain.com).`,
            inputmode: 'email',
            maxlength: 254,
        },

        url: {
            test: (v) => {
                try {
                    const url = new URL(v);
                    return url.protocol === 'http:' || url.protocol === 'https:';
                } catch { return false; }
            },
            message: (name) => `${name} must be a valid URL (e.g., https://example.com).`,
            inputmode: 'url',
            maxlength: 2048,
        },

        number: {
            test: (v) => /^-?\d+$/.test(v.trim()),
            message: (name) => `${name} must be a valid whole number.`,
            inputmode: 'numeric',
        },

        decimal: {
            test: (v) => {
                const clean = String(v).replace(/,/g, '');
                return /^-?\d+(\.\d{1,2})?$/.test(clean);
            },
            message: (name) => `${name} must be a valid decimal number with up to 2 decimal places.`,
            inputmode: 'decimal',
            format: (v) => {
                let cleaned = String(v).replace(/[^0-9.-]/g, '');
                const parts = cleaned.split('.');
                if (parts.length > 2) {
                    cleaned = parts[0] + '.' + parts.slice(1).join('');
                }
                const isNegative = cleaned.startsWith('-');
                cleaned = cleaned.replace(/-/g, '');
                const decimalParts = cleaned.split('.');
                let integerPart = decimalParts[0] || '';
                let decimalPart = decimalParts[1] || '';
                if (decimalPart.length > 2) {
                    decimalPart = decimalPart.slice(0, 2);
                }
                if (integerPart) {
                    integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
                }
                let result = '';
                if (isNegative && (integerPart || decimalPart)) {
                    result = '-';
                }
                result += integerPart;
                if (decimalPart) {
                    result += '.' + decimalPart;
                }
                return result;
            },
        },

        percentage: {
            test: (v) => {
                // Remove commas and percentage signs
                const clean = String(v).replace(/,/g, '').replace(/%/g, '').trim();
                if (!/^-?\d+(\.\d{1,2})?$/.test(clean)) {
                    return false;
                }
                const num = parseFloat(clean);
                return !isNaN(num) && num >= 0 && num <= 100;
            },
            message: (name) => `${name} must be a valid percentage between 0 and 100, with up to 2 decimal places.`,
            inputmode: 'decimal',
            maxlength: 10,
            format: (v) => {
                let cleaned = String(v).replace(/[^0-9.-]/g, '');
                const parts = cleaned.split('.');
                if (parts.length > 2) {
                    cleaned = parts[0] + '.' + parts.slice(1).join('');
                }
                const isNegative = cleaned.startsWith('-');
                cleaned = cleaned.replace(/-/g, '');
                const decimalParts = cleaned.split('.');
                let integerPart = decimalParts[0] || '';
                let decimalPart = decimalParts[1] || '';
                if (decimalPart.length > 2) {
                    decimalPart = decimalPart.slice(0, 2);
                }
                if (integerPart.length > 3) {
                    integerPart = integerPart.slice(0, 3);
                }
                if (integerPart) {
                    integerPart = integerPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
                }
                let result = '';
                if (isNegative) {
                    result = '';
                }
                result += integerPart;
                if (decimalPart) {
                    result += '.' + decimalPart;
                }
                if (result === '' || result === '.') {
                    return '';
                }
                return result;
            },
        },

        year: {
            test: (v) => /^[0-9]{4}$/.test(v),
            message: (name) => `${name} must be a valid 4-digit year (e.g., 2024).`,
            pattern: '[0-9]{4}',
            inputmode: 'numeric',
            maxlength: 4,
            format: (v) => String(v).replace(/[^0-9]/g, '').slice(0, 4),
        },

        financial_year: {
            test: (v) => /^[0-9]{4}-[0-9]{4}$/.test(v),
            message: (name) => `${name} must be in format YYYY-YYYY (e.g., 2024-2025).`,
            maxlength: 9,
            format: (v) => {
                let cleaned = String(v).replace(/[^0-9-]/g, '');
                const parts = cleaned.split('-');
                if (parts.length > 2) {
                    cleaned = parts[0] + '-' + parts.slice(1).join('');
                }
                return cleaned.slice(0, 9);
            }
        },

        cin: {
            test: (v) => /^[A-Z0-9]{21}$/.test(v),
            message: (name) => `${name} must be a valid 21-character Corporate Identification Number.`,
            maxlength: 21,
            format: (v) => String(v).toUpperCase().replace(/[^A-Z0-9]/g, ''),
        },

        pan: {
            test: (v) => /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/.test(v),
            message: (name) => `${name} must be a valid 10-character PAN (e.g., ABCDE1234F).`,
            maxlength: 10,
            format: (v) => String(v).toUpperCase().replace(/[^A-Z0-9]/g, ''),
        },

        gst: {
            test: (v) => /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}[Z]{1}[0-9A-Z]{1}$/.test(v),
            message: (name) => `${name} must be a valid 15-character GSTIN.`,
            maxlength: 15,
            format: (v) => String(v).toUpperCase().replace(/[^A-Z0-9]/g, ''),
        },

        aadhaar: {
            test: (v) => /^[0-9]{12}$/.test(v),
            message: (name) => `${name} must be a valid 12-digit Aadhaar number.`,
            pattern: '[0-9]{12}',
            inputmode: 'numeric',
            maxlength: 12,
            format: (v) => String(v).replace(/[^0-9]/g, '').slice(0, 12),
        },

        pin_code: {
            test: (v) => /^[0-9]{6}$/.test(v),
            message: (name) => `${name} must be a valid 6-digit PIN code.`,
            pattern: '[0-9]{6}',
            inputmode: 'numeric',
            maxlength: 6,
            format: (v) => String(v).replace(/[^0-9]/g, '').slice(0, 6),
        },

        ifsc: {
            test: (v) => /^[A-Z]{4}0[A-Z0-9]{6}$/.test(v),
            message: (name) => `${name} must be a valid 11-character IFSC code (e.g., SBIN0001234).`,
            maxlength: 11,
            format: (v) => String(v).toUpperCase().replace(/[^A-Z0-9]/g, ''),
        },

        account_number: {
            test: (v) => /^[0-9]{9,18}$/.test(v),
            message: (name) => `${name} must be a valid account number (9-18 digits).`,
            inputmode: 'numeric',
            maxlength: 18,
            format: (v) => String(v).replace(/[^0-9]/g, ''),
        },

        number_with_unit: {
            test: (v) => {
                // Remove commas and clean the input
                const clean = String(v).replace(/,/g, '').trim().toLowerCase();
                // Allow numbers with optional decimal and unit (cr, crore, lakh, thousand, k, m)
                return /^(\d+(\.\d+)?)\s*(cr|crore|lakh|thousand|k|m)?$/i.test(clean);
            },
            message: (name) => `${name} must be a valid number with optional unit (cr, crore, lakh, thousand, k, m).`,
            inputmode: 'text',
            maxlength: 50,
            format: (v) => {
                // If the value is empty, return it
                if (!v) return v;
                
                // If the input is just letters (unit being typed), return it as-is
                if (/^[a-zA-Z]+$/.test(v)) {
                    return v;
                }
                
                // For mixed input, format the number part but preserve the unit
                // Extract number and unit parts
                let numberPart = '';
                let unitPart = '';
                
                // Try to match number with commas and optional unit
                const match = v.match(/^([\d,]*\.?[\d,]*)\s*([a-zA-Z]*)$/);
                if (match) {
                    numberPart = match[1] || '';
                    unitPart = match[2] || '';
                } else {
                    // If no match, just return the input as-is
                    return v;
                }
                
                // If there's no number part, return the input as-is
                if (!numberPart) return v;
                
                // Remove commas to process the number
                const rawNumber = numberPart.replace(/,/g, '');
                
                // If there's no valid number, return the input as-is
                if (!rawNumber || !/^\d*\.?\d*$/.test(rawNumber)) {
                    return v;
                }
                
                // Split integer and decimal parts
                const parts = rawNumber.split('.');
                let intPart = parts[0] || '0';
                const decPart = parts[1] || '';
                
                // Remove leading zeros
                if (intPart.length > 1 && intPart.startsWith('0')) {
                    intPart = intPart.replace(/^0+/, '');
                    if (intPart === '') intPart = '0';
                }
                
                // Format integer part with commas (only if it's a valid number)
                let formattedInt = intPart;
                if (intPart && intPart !== '0' && /^\d+$/.test(intPart)) {
                    formattedInt = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
                }
                
                // Limit decimal places to 2
                const formattedDec = decPart.slice(0, 2);
                
                // Build the formatted number
                let formattedNumber = formattedInt;
                if (formattedDec) {
                    formattedNumber += '.' + formattedDec;
                }
                
                // Combine number and unit
                return formattedNumber + (unitPart ? ' ' + unitPart : '');
            }
        },

        text: {
            test: (v) => true,
            message: (name) => `${name} is required.`,
        },

        textarea: {
            test: (v) => true,
            message: (name) => `${name} is required.`,
        },

    };

    // ============================================================
    // 2. HELPER FUNCTIONS
    // ============================================================

    /**
     * Format a value as percentage with 2 decimal places
     */
    function formatPercentageValue(value) {
        if (value === null || value === undefined || value === '') return '';
        const num = parseFloat(value);
        if (isNaN(num) || !isFinite(num)) return '';
        const rounded = Math.round(num * 100) / 100;
        if (rounded % 1 === 0) {
            return rounded.toString();
        }
        return rounded.toFixed(2);
    }

    /**
     * Get validator for a field type
     */
    function getValidator(fieldType) {
        return VALIDATORS[fieldType] || null;
    }

    /**
     * Validate a single field
     * Returns { valid: boolean, message: string }
     */
    function validateField(element) {
        const fieldType = element.dataset.validation || 'text';
        const isRequired = element.dataset.required === 'true';
        const fieldName = element.dataset.fieldName || 'Field';
        const value = element.value || '';

        // For radio buttons, get the group value
        let actualValue = value;
        if (element.type === 'radio') {
            const groupName = element.name;
            const checked = document.querySelector(`input[name="${groupName}"]:checked`);
            actualValue = checked ? checked.value : '';
        } else if (element.type === 'checkbox' && element.closest('.choice-stack')) {
            // Checkbox group: collect all checked values
            const groupName = element.dataset.fieldName;
            const checkedBoxes = document.querySelectorAll(`input[type="checkbox"][data-field-name="${groupName}"]:checked`);
            actualValue = Array.from(checkedBoxes).map(el => el.value).join(',');
        }

        const validator = getValidator(fieldType);

        // If not required and empty, skip validation (no error)
        if (!isRequired && (actualValue === '' || actualValue === null || actualValue === undefined)) {
            return { valid: true, message: '' };
        }

        // If required and empty, show required message
        if (isRequired && (actualValue === '' || actualValue === null || actualValue === undefined)) {
            return { valid: false, message: `${fieldName} is required.` };
        }

        // Apply validator if available
        if (validator && typeof validator.test === 'function') {
            const valid = validator.test(actualValue);
            const message = valid ? '' : (typeof validator.message === 'function' ? validator.message(fieldName) : validator.message);
            return { valid, message };
        }

        // No validator found, assume valid
        return { valid: true, message: '' };
    }

    /**
     * Show validation state on an element
     */
    function showValidation(element, valid, message, forceShow = false) {
        const formGroup = element.closest('.form-group, td, .table-cell');
        if (!formGroup) return;

        const feedback = formGroup.querySelector('.invalid-feedback');
        const input = element;
        
        // Check if field has been blurred (touched)
        const isBlurred = element.dataset.blurred === 'true';
        
        // Only show error if:
        // 1. forceShow is true (form submission), OR
        // 2. Field has been blurred AND (it's invalid OR it's valid with content)
        const shouldShow = forceShow || isBlurred;

        if (!shouldShow) {
            // Field hasn't been blurred yet - keep clean state
            formGroup.classList.remove('has-error');
            if (input) {
                input.classList.remove('is-invalid');
                input.classList.remove('is-valid');
            }
            if (feedback) {
                feedback.textContent = '';
                feedback.style.display = 'none';
            }
            return;
        }

        // Field has been blurred - show validation state
        if (!valid && message) {
            formGroup.classList.add('has-error');
            if (input) {
                input.classList.add('is-invalid');
                input.classList.remove('is-valid');
            }
            if (feedback) {
                feedback.textContent = message;
                feedback.style.display = 'block';
            }
        } else {
            formGroup.classList.remove('has-error');
            if (input) {
                input.classList.remove('is-invalid');
                // Only show is-valid if field has content
                if (element.value && String(element.value).trim() !== '') {
                    input.classList.add('is-valid');
                } else {
                    input.classList.remove('is-valid');
                }
            }
            if (feedback) {
                feedback.textContent = '';
                feedback.style.display = 'none';
            }
        }
    }

    /**
     * Clear validation state on an element
     */
    function clearValidation(element) {
        const formGroup = element.closest('.form-group, td, .table-cell');
        if (!formGroup) return;

        const feedback = formGroup.querySelector('.invalid-feedback');
        const input = element;

        formGroup.classList.remove('has-error');
        if (input) {
            input.classList.remove('is-invalid');
            input.classList.remove('is-valid');
        }
        if (feedback) {
            feedback.textContent = '';
            feedback.style.display = 'none';
        }
        // Reset blurred state
        element.dataset.blurred = 'false';
    }

    /**
     * Mark field as blurred
     */
    function markBlurred(element) {
        element.dataset.blurred = 'true';
        
        // For radio groups, mark all radios in group as blurred
        if (element.type === 'radio') {
            const groupName = element.name;
            document.querySelectorAll(`input[name="${groupName}"]`).forEach(input => {
                input.dataset.blurred = 'true';
            });
        }
        
        // For checkbox groups, mark all checkboxes in group as blurred
        if (element.type === 'checkbox' && element.closest('.choice-stack')) {
            const groupName = element.dataset.fieldName;
            document.querySelectorAll(`input[type="checkbox"][data-field-name="${groupName}"]`).forEach(input => {
                input.dataset.blurred = 'true';
            });
        }
    }

    /**
     * Attach validation events to an element
     */
    function attachValidation(element) {
        if (!element) return;

        // Skip elements that already have validation attached
        if (element._validationAttached) return;
        element._validationAttached = true;

        // Initialize blurred state
        element.dataset.blurred = 'false';

        // On blur, mark as blurred and validate
        element.addEventListener('blur', function(e) {
            markBlurred(this);
            
            // For radios, validate the group
            if (this.type === 'radio') {
                const groupName = this.name;
                const groupInputs = document.querySelectorAll(`input[name="${groupName}"]`);
                groupInputs.forEach(input => {
                    if (input._validationAttached) {
                        const result = validateField(input);
                        showValidation(input, result.valid, result.message, false);
                    }
                });
                return;
            }

            // For checkboxes in groups
            if (this.type === 'checkbox' && this.closest('.choice-stack')) {
                const groupName = this.dataset.fieldName;
                const groupInputs = document.querySelectorAll(`input[type="checkbox"][data-field-name="${groupName}"]`);
                groupInputs.forEach(input => {
                    if (input._validationAttached) {
                        const result = validateField(input);
                        showValidation(input, result.valid, result.message, false);
                    }
                });
                return;
            }

            const result = validateField(this);
            showValidation(this, result.valid, result.message, false);
        });

        // On input, only validate if field has been blurred
        element.addEventListener('input', function(e) {
            // For radios and checkboxes, this is handled by their blur/change events
            if (this.type === 'radio' || (this.type === 'checkbox' && this.closest('.choice-stack'))) {
                return;
            }
            
            // Only validate if field has been blurred before
            if (this.dataset.blurred === 'true') {
                const result = validateField(this);
                showValidation(this, result.valid, result.message, false);
            }
        });

        element.addEventListener('change', function(e) {
            if (this.type === 'radio' || this.type === 'checkbox') {
                if (this.dataset.blurred === 'true') {
                    markBlurred(this);
                    
                    if (this.type === 'radio') {
                        const groupName = this.name;
                        const groupInputs = document.querySelectorAll(`input[name="${groupName}"]`);
                        groupInputs.forEach(input => {
                            if (input._validationAttached) {
                                const result = validateField(input);
                                showValidation(input, result.valid, result.message, false);
                            }
                        });
                        return;
                    }
                    
                    if (this.type === 'checkbox' && this.closest('.choice-stack')) {
                        const groupName = this.dataset.fieldName;
                        const groupInputs = document.querySelectorAll(`input[type="checkbox"][data-field-name="${groupName}"]`);
                        groupInputs.forEach(input => {
                            if (input._validationAttached) {
                                const result = validateField(input);
                                showValidation(input, result.valid, result.message, false);
                            }
                        });
                        return;
                    }
                }
                return;
            }
            
            if (this.dataset.blurred === 'true') {
                const result = validateField(this);
                showValidation(this, result.valid, result.message, false);
            }
        });

        // On paste, validate only if already blurred
        element.addEventListener('paste', function(e) {
            if (this.dataset.blurred === 'true') {
                // Use setTimeout to let the paste complete
                setTimeout(() => {
                    const result = validateField(this);
                    showValidation(this, result.valid, result.message, false);
                }, 10);
            }
        });

        // Restrict input based on field type (only for specific types)
        // FIXED: Better cursor position handling
        element.addEventListener('input', function(e) {
            const fieldType = this.dataset.validation || 'text';
            const validator = getValidator(fieldType);
            if (validator && typeof validator.format === 'function') {
                const oldValue = this.value;
                const cursorPos = this.selectionStart;
                const newValue = validator.format(oldValue);
                if (newValue !== oldValue) {
                    // Calculate how many characters were added/removed before the cursor
                    const diff = newValue.length - oldValue.length;
                    this.value = newValue;
                    // Adjust cursor position by the difference, but clamp to valid range
                    const newCursorPos = Math.max(0, Math.min(cursorPos + diff, newValue.length));
                    this.setSelectionRange(newCursorPos, newCursorPos);
                }
            }
        });

        if (element.closest('td') && element.dataset.formula) {
            element.addEventListener('input', function(e) {
                const event = new CustomEvent('table-cell-change', {
                    detail: { element: this }
                });
                document.dispatchEvent(event);
            });
        }
    }

    /**
     * Perform validation on an element with force show
     */
    function performValidation(element, forceShow = false) {
        const result = validateField(element);
        showValidation(element, result.valid, result.message, forceShow);
        return result.valid;
    }

    // ============================================================
    // 3. FORM VALIDATION
    // ============================================================

    /**
     * Validate entire form
     * Returns true if all fields are valid
     */
    function validateForm() {
        const inputs = document.querySelectorAll('[data-validation]');
        let allValid = true;

        // Process all visible input groups
        const groups = new Set();
        inputs.forEach(input => {
            // For radios, validate the group once
            if (input.type === 'radio') {
                const groupName = input.name;
                if (groups.has(groupName)) return;
                groups.add(groupName);
                const groupInputs = document.querySelectorAll(`input[name="${groupName}"]`);
                const firstInput = groupInputs[0];
                if (firstInput && firstInput.closest('.form-group')) {
                    // Mark all as blurred before validation
                    groupInputs.forEach(inp => inp.dataset.blurred = 'true');
                    const result = validateField(firstInput);
                    showValidation(firstInput, result.valid, result.message, true);
                    if (!result.valid) allValid = false;
                }
                return;
            }
            // For checkbox groups

            if (input.type === 'checkbox' && input.closest('.choice-stack')) {
                const groupName = input.dataset.fieldName;
                const groupKey = `checkbox_${groupName}`;
                if (groups.has(groupKey)) return;
                groups.add(groupKey);
                const groupInputs = document.querySelectorAll(`input[type="checkbox"][data-field-name="${groupName}"]`);
                const firstInput = groupInputs[0];
                    // Mark all as blurred before validation
                if (firstInput && firstInput.closest('.form-group')) {
                    groupInputs.forEach(inp => inp.dataset.blurred = 'true');
                    const result = validateField(firstInput);
                    showValidation(firstInput, result.valid, result.message, true);
                    if (!result.valid) allValid = false;
                }
                return;
            // Regular inputs - mark as blurred before validation
            }

            input.dataset.blurred = 'true';
            const result = validateField(input);
            showValidation(input, result.valid, result.message, true);
            if (!result.valid) allValid = false;
        });

        return allValid;
    }

    // ============================================================
    // 4. AUTO-ATTACH ON DYNAMIC CONTENT
    // ============================================================

    /**
     * Attach validation to all elements in a container
     */
    function attachValidationToContainer(container) {
        if (!container) return;
        const inputs = container.querySelectorAll('[data-validation]');
        inputs.forEach(input => attachValidation(input));
    }

    // ============================================================
    // 5. PUBLIC API
        // Core functions
    // ============================================================

    window.BRSRValidation = {
        getValidator: getValidator,
        validateField: validateField,
        validateForm: validateForm,
        showValidation: showValidation,
        // Attachment
        clearValidation: clearValidation,
        performValidation: performValidation,
        markBlurred: markBlurred,
        // Validator registry
        attachValidation: attachValidation,
        attachValidationToContainer: attachValidationToContainer,
        validators: VALIDATORS,
        formatPercentageValue: formatPercentageValue,
    };

    // ============================================================
    // 6. DOM READY - AUTO-INIT
    // Auto-attach to existing inputs when DOM is ready
        // Attach to all existing validation inputs
    // ============================================================
        // Watch for new content via MutationObserver
    document.addEventListener('DOMContentLoaded', function() {
        const inputs = document.querySelectorAll('[data-validation]');
        inputs.forEach(input => attachValidation(input));

        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(mutation => {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === 1) {
                        if (node.hasAttribute && node.hasAttribute('data-validation')) {
                            attachValidation(node);
                        }
                        const descendants = node.querySelectorAll ? node.querySelectorAll('[data-validation]') : [];
                        descendants.forEach(el => attachValidation(el));
                    }
                });
            });
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true,
        });
    });

})();
