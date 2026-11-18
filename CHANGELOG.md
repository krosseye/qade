# CHANGELOG

<!-- version list -->

## v0.3.0 (2026-11-18)

### Bug Fixes

- Centre thin pulse waves so their fades don't thump
  ([`a4e4c01`](https://github.com/krosseye/qade/commit/a4e4c01bdff177b96c9fc05c1c810da4a0af6a08))

- Spawn bear near centre of maze
  ([`51cf87a`](https://github.com/krosseye/qade/commit/51cf87a827cd95664a1a381b82a4539e1be53c70))

### Chores

- Exclude the music guide from ruff format
  ([`388b877`](https://github.com/krosseye/qade/commit/388b877ebdc1c4db46afb6fdd1904c195ea0599c))

### Documentation

- Add a music guide and reference
  ([`87f5664`](https://github.com/krosseye/qade/commit/87f56640c4e492e115224340fe42c419b301556f))

- Add music examples for the sound chip
  ([`8a2d59a`](https://github.com/krosseye/qade/commit/8a2d59a7df7e2feae45fcac54597849cf924e231))

### Features

- Add grizzly_depths
  ([`c07c8f7`](https://github.com/krosseye/qade/commit/c07c8f7e7eb1b7d048f8b7da288bc5127f64a35a))

- Draw ceiling grid
  ([`062d226`](https://github.com/krosseye/qade/commit/062d226ee57d877d44ca74d9cbe1c4af99649fbd))

- Give the tunnels landmarks to recognise
  ([`ee16b21`](https://github.com/krosseye/qade/commit/ee16b21b6b3413403ff5149468936f11b9711152))

- Place the exit at a away far cell and the lair between it and the start
  ([`e2a18af`](https://github.com/krosseye/qade/commit/e2a18afd297ddfb44c92fe7b3ccbf08a4901858b))

- Play songs on the sound chip
  ([`0cafbd8`](https://github.com/krosseye/qade/commit/0cafbd8bc336662bc95e059926f54c716c5552ac))

- Score the walls near the lair with claw marks
  ([`57a49fb`](https://github.com/krosseye/qade/commit/57a49fb6f1fa7a1471b8233bd0ac7dc6da3d8055))

- Swap music tracks, and let stings hand back
  ([`6ffe3e0`](https://github.com/krosseye/qade/commit/6ffe3e08c3a3f6556ae24cfcfccb85966a9e4a58))

- Wake a sleeping bear that is stumbled into instead of ending the run
  ([`4c3eaf8`](https://github.com/krosseye/qade/commit/4c3eaf85eef27ff38676eac26a30f7e7e87c0d30))

### Refactoring

- Move the WAV cache out of the sound bus
  ([`78a195c`](https://github.com/krosseye/qade/commit/78a195cee8a5c0510fec13b6db29ff7feff71f7f))

### Testing

- Add grizzly's tests
  ([`76ea1ef`](https://github.com/krosseye/qade/commit/76ea1ef9493face120937ee34dae37b91384366e))


## v0.2.0 (2026-11-14)

### Bug Fixes

- Handle empty or unparseable accent colour
  ([`1d3d3f0`](https://github.com/krosseye/qade/commit/1d3d3f02c9696c713d8796cc0d33a88e5fe0706a))

- Restore antialiasing setting used by host
  ([`c0050e0`](https://github.com/krosseye/qade/commit/c0050e064719478f3b3cd1a0ccc35710706462c7))

### Features

- Add qade_launcher
  ([`9bdbc34`](https://github.com/krosseye/qade/commit/9bdbc34d7ff024a3b3f2e32a5da2feb8e0224762))

### Testing

- Add launcher test suite
  ([`5b2e861`](https://github.com/krosseye/qade/commit/5b2e861d3e981f6b17ec5d972a56515a9a27229c))


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
