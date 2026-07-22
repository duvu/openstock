## ADDED Requirements

### Requirement: FiinQuantX has no approval gate

The system SHALL allow FiinQuantX runtime access when the exact supported SDK
and local credentials are available. It SHALL allow vnalpha persistence for
explicit `FIINQUANTX` source requests without an approval boolean, reference,
fingerprint or expiry environment variable.

#### Scenario: Supported SDK and credentials permit provider I/O

- **WHEN** the exact supported FiinQuantX SDK and local credentials are
  configured
- **THEN** the provider may create a session and execute an allowlisted request
- **AND THEN** no approval-related environment variable is read or required.

#### Scenario: Persistence accepts FiinQuantX without approval configuration

- **WHEN** vnalpha validates a warehouse-bound request with source `FIINQUANTX`
- **THEN** it accepts the source without approval-related environment
  configuration.
