# CHANGELOG

<!-- version list -->

## v0.1.1 (2026-11-14)

### Bug Fixes

- Handle numeric edge cases in particles and gamepad input
  ([`0b52def`](https://github.com/krosseye/qade/commit/0b52defd84b449c4f29106eb027942243a8bbd1a))

- Harden the game loop against bad clock readings
  ([`b2e7a42`](https://github.com/krosseye/qade/commit/b2e7a426d4ccfaec0f8c43f2a4aab41c7d16c9bb))

- Solve spring_step exactly so it is stable at any step
  ([`e42ba38`](https://github.com/krosseye/qade/commit/e42ba38386c0d027c6e2ae187f7f1127ce1b26ee))

### Build System

- Require Python 3.12 or newer
  ([`faaf01a`](https://github.com/krosseye/qade/commit/faaf01a377f00e72f893bc6937545a432d07e4e6))

### Chores

- **deps-dev**: Update uv-build requirement
  ([`fe47247`](https://github.com/krosseye/qade/commit/fe47247c0ded77bc72e6c3eb266bc1b3e5c91259))

### Continuous Integration

- Bump actions/checkout from 5 to 7
  ([`a556111`](https://github.com/krosseye/qade/commit/a55611176e1095181278796a7e830363341b123b))

- Bump actions/deploy-pages from 4 to 5
  ([`4e8aabd`](https://github.com/krosseye/qade/commit/4e8aabd112908dbf731ce08409708853be7b9533))

- Bump actions/upload-pages-artifact from 4 to 5
  ([`6d0fc24`](https://github.com/krosseye/qade/commit/6d0fc24da9fb32604a41dc65d09b6d2a9b7ef5fa))

- Bump astral-sh/setup-uv from 6 to 7
  ([`9ca338d`](https://github.com/krosseye/qade/commit/9ca338dea37b3286bd567e7352e715216c2e2bd4))

### Refactoring

- Use updated type parameters in state machine
  ([`cc3c1cd`](https://github.com/krosseye/qade/commit/cc3c1cd5c31f8577c8f7462cb5fa6276fb290012))

### Testing

- Add test suite for rendering, timing, collision, input and lifecycle
  ([`aab6902`](https://github.com/krosseye/qade/commit/aab6902f256ba96ae23c8b62c4586733764eab77))


## v0.1.0 (2026-11-14)

- Initial Release
