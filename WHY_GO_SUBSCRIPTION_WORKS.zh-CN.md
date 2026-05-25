# 为什么 Hermes 直连会出问题，而 Pi provider 和这个 provider 可以工作

这份说明解释的是：为什么 Command Code Go 订阅在 Hermes 里按“普通 provider API”方式直连会失败，但 `pi-commandcode-provider` 和本项目的 Hermes bridge 可以正常使用。

## 核心结论

Command Code Go 订阅可以登录 Command Code CLI，也可以通过 Command Code 面向订阅用户的生成通道使用模型；但它不包含直接调用 Command Code provider API 的权限。

所以问题不在于 Hermes 不能接 Command Code，也不在于模型名本身不可用，而是在于“走了哪条接口路径”：

| 方式 | 请求路径 | Go 订阅是否适合 | 结果 |
| --- | --- | --- | --- |
| Hermes 直接连 Command Code provider API | `provider/v1` 一类的 API provider 通道 | 不适合 | 会被 API 权限检查拦住 |
| Pi + `pi-commandcode-provider` | Command Code CLI/订阅可用的生成通道 | 适合 | 可以使用 |
| Hermes + 本项目 bridge | Hermes 先连本地 OpenAI-compatible bridge，再由 bridge 走订阅可用的生成通道 | 适合 | 可以使用 |

## 原本的 Hermes 连接方式为什么会失败

Hermes 的 provider 系统通常期待一个 OpenAI-compatible API，例如：

```text
Hermes -> provider base_url -> /chat/completions
```

如果直接把 Command Code 配成一个普通 API provider，Hermes 会按 provider API 的方式发请求。这个路径对 Command Code 来说属于“直接 API access”。

Go 订阅的问题在这里：它可以用于 Command Code CLI 登录和订阅内使用，但不包含直接 provider API 权限。因此请求会在 Command Code 的权限层被拒绝，典型表现就是类似：

```text
Go plan doesn't include API access
```

或者在 Hermes 侧表现成 provider 不可用、模型无法正常响应。

另外，如果 Hermes 里没有显式定义 `commandcode` provider，还会先遇到另一个更早的问题：

```text
Unknown provider 'commandcode'
```

这个错误表示 Hermes 配置里根本没有叫 `commandcode` 的 provider。即使补上 provider 定义，如果它指向的是 Command Code 的直接 provider API，Go 订阅仍然会卡在 API 权限上。

## Pi provider 为什么可以

`pi-commandcode-provider` 的关键点不是“它叫 Pi”，而是它没有把 Go 订阅当成普通 provider API 来用。

它使用的是 Command Code 对 CLI/订阅用户可用的生成通道。这个通道和直接 provider API 不是同一个权限面：

```text
Pi -> pi-commandcode-provider -> Command Code 订阅可用生成通道 -> 模型
```

因此，只要账号本身有有效的 Command Code Go 订阅，并且本机已经完成 Command Code 登录，Pi provider 就可以借助这条订阅可用路径工作。

## 本项目为什么可以

Hermes 需要的是一个它能识别的 provider，所以本项目在本机启动一个 OpenAI-compatible bridge：

```text
Hermes -> http://127.0.0.1:8788/v1 -> hermes-commandcode bridge -> Command Code 订阅可用生成通道 -> 模型
```

Hermes 看到的是一个本地的 OpenAI-compatible endpoint：

```text
http://127.0.0.1:8788/v1
```

这个本地 bridge 负责做几件事：

- 读取本机已有的 Command Code 登录信息
- 接收 Hermes 发来的 OpenAI Chat Completions 风格请求
- 转换成 Command Code 订阅可用生成通道能理解的请求
- 把返回内容再转换回 Hermes 期望的格式
- 提供 `/v1/models`，让 Hermes 能看到模型列表和上下文长度
- 在 streaming 时补齐 `usage` 信息，让 Hermes 的上下文和 token 统计能正常显示
- 转换 tool calls，保证 Hermes 的工具调用流程能跑通

所以它不是让 Go 订阅获得了直接 provider API 权限，而是让 Hermes 使用一条 Go 订阅本来就可以使用的路径。

## 三种方式的请求流程对比

### 1. 原本直连方式

```text
Hermes
  -> Command Code provider API
  -> API entitlement check
  -> Go 订阅没有 direct API access
  -> 请求失败
```

### 2. Pi provider

```text
Pi
  -> pi-commandcode-provider
  -> Command Code 订阅可用生成通道
  -> 模型响应
```

### 3. 本项目

```text
Hermes
  -> 本地 OpenAI-compatible bridge
  -> Command Code 订阅可用生成通道
  -> bridge 转回 Hermes 需要的格式
  -> Hermes 正常显示结果、上下文和工具调用
```

## 这个项目解决了什么

这个项目主要解决四类问题：

1. Hermes 不认识 `commandcode` provider。
2. Hermes 直连 Command Code provider API 会被 Go 订阅的 API 权限限制拦住。
3. Hermes 需要模型元数据，例如 `context_length`，否则上下文长度显示可能不正常。
4. Hermes 需要标准的 streaming、usage 和 tool call 格式，否则会出现统计缺失或工具调用异常。

## 这个项目不是什么

这个项目不是 Command Code 官方 provider，也不是新的 Command Code API 权限。

它依赖的是你自己已经拥有的有效 Command Code 订阅和本机登录状态。它只是把 Hermes 的 provider 请求转换到 Go 订阅可用的本地使用路径上。

如果 Command Code 以后调整订阅接口、鉴权方式或返回事件格式，这个 bridge 也可能需要跟着更新。

