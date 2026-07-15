# Edge Cases Fixture

Expected highlights:

- `.env` excluded as a secret path
- binary file excluded
- oversized file can be covered by tests with a lower configured limit
- shell/process and filesystem write candidates detected
- dynamic lookup detected as unknown
