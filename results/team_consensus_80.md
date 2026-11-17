# 正式回答实验：研究团队共识评阅记录

## 记录来源

2026-11-15，Codex 在隐藏左右组别的条件下逐对起草判断与理由；作者和同伴审阅了评价口径及判断，并表示认可，将这些判断作为研究团队采用的共识评价。以下保留原始逐项记录及其形成过程。该记录是团队采纳的共识结果，不是两名评阅者各自独立填写的盲评数据，也不用于计算评阅者间一致性。

评价重点：必要内容是否保留、额外内容是否有用、历史信息是否正确用于当前问题。关键技术错误单列，不将回答长短直接视为优势。

## 汇总

| 对照 | F 更好 | 对照更好 | 持平 | 双方关键错误 |
|---|---:|---:|---:|---:|
| F 对 B（40 对） | 15 | 16 | 7 | 2 |
| F 对 E（40 对） | 11 | 18 | 9 | 2 |

## 逐项记录

左、右是评阅时的匿名位置；研究组别在评阅完成后按内部映射揭盲。理由沿用形成共识时的原始措辞，便于追溯。

| 对号 | 对照 | 用户 | 左组 | 右组 | 判断 | 左关键错误 | 右关键错误 | 理由 |
|---|---|---|---|---|---|---|---|---|
| PC3DF7ADCCF | F 对 B | U055 | F | B | 左较好 | 否 | 否 | left gives staging and certificate verification; right adds generic service setup; left imports Snipe-IT from history as an unconfirmed example |
| P89BDD3763B | F 对 B | U068 | F | B | 右较好 | 否 | 否 | right centers checks for ZooKeeper container, port, logs; left speculates about slave Marathon; need full-log check for IP discrepancy |
| P88D2D3B032 | F 对 E | U078 | E | F | 左较好 | 否 | 否 | both fix nginx foreground; left notices PHP-FPM from Dockerfile; right suggests official nginx image despite Ubuntu base |
| PC3C527A887 | F 对 B | U028 | F | B | 左较好 | 否 | 否 | left mounts host tests only, keeps application code in image; right also mounts host code and is unnecessarily long |
| P38AB589371 | F 对 B | U086 | F | B | 持平 | 否 | 否 | both separate Nginx, PHP-FPM, Redis, MySQL, Elasticsearch and use Compose; differences are minor for stated question |
| PF144192F10 | F 对 E | U050 | E | F | 持平 | 否 | 否 | both offer speculative VirtualBox troubleshooting with destructive cleanup risk; needs historical version verification |
| PA2A90F48F9 | F 对 E | U082 | F | E | 右较好 | 否 | 否 | both fix server max_allowed_packet; right checks oversized statement in 16 GB dump; right separates runtime validation and persistent fix |
| PE805F866BB | F 对 E | U004 | E | F | 持平 | 否 | 否 | both correctly wire entrypoint.sh; left notes bind-mount shadowing; right notes DB readiness; each adds different useful caveat |
| P3228410FF2 | F 对 E | U022 | E | F | 右较好 | 是 | 否 | right uses existing .env and docker-compose config evidence; left incorrectly dismisses inline environment with args |
| P25A6C8D863 | F 对 E | U076 | E | F | 左较好 | 否 | 是 | both check registry HTTP and v2; left uses public port 7073; right sets registry_external_url to internal 4567 despite client 7073 |
| PA374FFD44E | F 对 B | U078 | B | F | 左较好 | 否 | 是 | 两侧都给出前台运行 nginx 的关键修复；右侧把当前 Ubuntu 自建镜像当成官方 nginx 镜像提供无效备选，左侧还提醒 PHP-FPM 启动。 |
| P3D2B91CA71 | F 对 B | U084 | B | F | 右较好 | 是 | 否 | 两侧都识别 -v 不能写在 Dockerfile RUN；左侧示例继续把 Docker socket 挂到 PostgreSQL socket 路径，右侧进一步区分两种 socket 并给出正确挂载位置。 |
| P9263414688 | F 对 E | U046 | E | F | 右较好 | 否 | 否 | 两侧都正确解释构建期与运行期；右侧给出完整入口脚本和默认命令，并说明重复执行与数据库就绪问题；默认启动命令仍需按实际基础镜像确认。 |
| P0E264B1E0C | F 对 B | U043 | B | F | 持平 | 否 | 否 | 两侧都抓住 27018:27017 端口映射并分别说明宿主机与容器网络地址；额外的连接检查差异不足以分出优劣。 |
| P49F505B5A2 | F 对 E | U055 | E | F | 左较好 | 否 | 否 | 两侧都给出 Ingress TLS Secret 和 cert-manager 路线；右侧直接把历史中的 Snipe-IT 当成当前应用并加入大量未经确认的部署细节，左侧更聚焦当前问题。 |
| PB3D24074D9 | F 对 B | U004 | F | B | 右较好 | 否 | 否 | 两侧都正确指出重复 command 只保留最后一项；右侧提醒挂载目录会覆盖镜像中复制的入口脚本，贴合当前配置；左侧附加 netcat 等依赖较重。 |
| P1EC72B8458 | F 对 E | U018 | F | E | 右较好 | 否 | 否 | 两侧都建议显式配置音乐目录；右侧使用题目中的 /Music 路径，给出更直接的运行命令，左侧误写 /music。 |
| P1B345205BA | F 对 E | U020 | E | F | 左较好 | 否 | 否 | 两侧都正确给出 liblzma-dev；左侧补上 Dockerfile 中安装依赖后继续 pip install 的完整顺序，右侧基本等效。 |
| P9478A9694A | F 对 E | U026 | E | F | 右较好 | 是 | 是 | 两侧均修正 proxy_pass 端口并辨认宿主机 nginx 日志；两侧都把脱敏后的数据库密码当作确定不匹配且建议删除卷，右侧对 502 原因解释更紧凑、少了左侧额外的用户组猜测。 |
| P18CDA721C6 | F 对 B | U001 | F | B | 持平 | 否 | 否 | 原 YAML 的 db/app 一空格缩进一致，关键是缺少 version 让旧版 Compose 按格式 1 解读；两侧都补 version 使示例可工作，但原因解释均不准。 |
| P5CE35402B4 | F 对 B | U060 | F | B | 左较好 | 否 | 否 | 两侧均指出 ENTRYPOINT 数组形式不执行 shell；左侧明确要求以 crm 所在目录设 PYTHONPATH，右侧未经当前题证据指定 /data/web 并当作最终推荐。 |
| P5EA44A5BFC | F 对 E | U062 | F | E | 持平 | 否 | 否 | 两侧都准确指出 net-tools 是 ifconfig 所属包并给出 apt-get update/install；其他示例价值很小。 |
| P96A6015BB7 | F 对 E | U070 | E | F | 右较好 | 是 | 否 | 两侧都注意到容器内 Meteor 监听 3000、宿主机却映射到容器 3003；左侧无证据断言默认 Compose 网络不通，右侧将 Mongo 连接失败列为另一项待查原因。 |
| P23B2F50C91 | F 对 B | U039 | F | B | 右较好 | 是 | 否 | 右侧识别官方 PHP 镜像从源码构建并给出 docker-php-ext-install bcmath；左侧错误断言官方镜像使用 Debian PHP 包。 |
| P8DB2C7A1ED | F 对 B | U058 | F | B | 右较好 | 否 | 否 | 两侧都提出 no-sandbox 与 /dev/shm 修复；右侧先给最小改动，左侧大段重装镜像且遗漏 unzip 依赖，步骤偏离问题。 |
| PD4B2F7EE8A | F 对 B | U024 | F | B | 双方关键错误 | 是 | 是 | 两侧都把递归 nextTick 报错直接断定为 inotify 限额并建议在镜像构建时写 sysctl；当前日志不足以支持这个确定诊断，缺少先隔离 watch/live reload 的检查。 |
| PC07EEAF688 | F 对 B | U035 | F | B | 右较好 | 否 | 否 | 两侧都准确区分 Windows 主机命令与 VM 内 shell；右侧直接给出退出 VM 再运行命令的步骤，较简洁。 |
| PF0A12AACCC | F 对 E | U048 | F | E | 左较好 | 否 | 是 | 两侧都解释空密码与认证规则问题；左侧建议直接用现有 psql 和真实凭据重试，右侧给出无效的 initdb 文件挂载示例且扩展过多。 |
| P4345671236 | F 对 E | U023 | F | E | 左较好 | 否 | 否 | 两侧都说明 Compose 可拉取私有仓库镜像；左侧直接给最小配置并补充登录与 HTTP registry 条件，右侧部署脚本偏冗长。 |
| PF57AF3C477 | F 对 E | U033 | F | E | 右较好 | 是 | 否 | 题目明确两份 Compose 同时运行；右侧正确说明合并后共享网络、移除 network_mode bridge，并修正 IPAM 缩进；左侧误判为两个独立网络，额外要求外部网络。 |
| PE85BE6C7AF | F 对 B | U050 | B | F | 持平 | 否 | 否 | 两侧都提供 VirtualBox 检查、残留 VM 清理和磁盘/权限排查，具体根因均未由日志证实；无需强分胜负。 |
| PD077CE299B | F 对 E | U051 | E | F | 右较好 | 否 | 否 | 两侧都建议在 qcow2 客体内安装 Docker 后保存镜像；右侧优先使用该年代 Ubuntu 14.04 的 docker.io 包，流程更直接。 |
| PF5FBF659F5 | F 对 E | U083 | E | F | 右较好 | 是 | 否 | 两侧都有流水线部署方案；左侧生产 Compose 仍把本地 ./core 挂载覆盖新镜像中的代码，破坏镜像更新，右侧移除源码挂载并区分环境变量。 |
| P0BD26AD989 | F 对 B | U036 | B | F | 左较好 | 否 | 否 | 两侧都找到了表单编码与 JSON 正文差异；左侧保留原代码的 baseURL 配置，右侧硬编码示例 IP，左侧更可复用。 |
| PD49D797C09 | F 对 B | U029 | F | B | 右较好 | 否 | 否 | 两侧都改用 Swarm 服务名访问 Logstash；右侧明确把 Ansible 变量从 IP 改为服务名，更贴合原问题且更简洁。 |
| PDD0721966F | F 对 E | U068 | F | E | 右较好 | 否 | 否 | 两侧都识别 Marathon 对 ZooKeeper 连接被拒并建议前台启动；右侧先核实容器、端口与 zoo.cfg，避免把 IP 不同直接解释成绑定错误。 |
| P791EF8A12F | F 对 B | U020 | F | B | 持平 | 否 | 否 | 两侧都准确补上 liblzma-dev 并重试 pip；后续背景解释差异很小。 |
| PF0BDC512C7 | F 对 B | U076 | F | B | 右较好 | 是 | 是 | 两侧都先给 /v2/ 检查且提出 HTTP registry 配置；但都把 registry_external_url 写为容器内 4567 而非客户端访问的 7073，右侧至少补充检查服务监听与容器配置，仍需人工复核。 |
| PE10DD7DC7E | F 对 E | U084 | E | F | 左较好 | 否 | 是 | 两侧都解释 RUN -v 与运行时卷挂载；右侧加入与题目无关且示例不可靠的 BuildKit 绑定挂载，左侧强调 Docker socket 与 PostgreSQL socket 不可混用。 |
| P5D0606DEC6 | F 对 B | U062 | F | B | 左较好 | 否 | 否 | 两侧都指出 net-tools 包名；左侧直接给安装命令与可持久化 Dockerfile，右侧历史记录引出的保存容器说明过长且非当前需求。 |
| P46D2F47276 | F 对 E | U086 | E | F | 右较好 | 否 | 否 | 两侧都建议按进程拆分并用 Compose 管理；右侧说明应用代码通常无需单独运行容器，方案比左侧另加数据容器清晰。 |
| PE12A781411 | F 对 B | U077 | F | B | 右较好 | 否 | 否 | 两侧均只能列可能原因；右侧先建议暴露调试日志、检查内存与 socket，左侧未经确认就建议关闭 SELinux 等较重操作。 |
| P31047D6415 | F 对 E | U012 | F | E | 持平 | 否 | 否 | 两侧都正确指出 Windows 2016 镜像 manifest 不匹配，不是实验模式问题；兼容镜像的具体旧标签未核实，暂无可靠优劣。 |
| PBCC954421A | F 对 B | U018 | B | F | 右较好 | 否 | 否 | 右侧将需要展示的音乐目录设计为显式配置，更符合实际目标；但示例路径写成 /music 而题目是 /Music，结论须按实际路径修正。 |
| P274B9D08E8 | F 对 B | U083 | B | F | 右较好 | 是 | 否 | 两侧给出 Bitbucket 到 EC2 的构建、推送和部署；左侧部署脚本 pull 后又使用 --build 本地重建，可能覆盖新镜像，右侧生产 Compose 引用远程镜像。 |
| P1061C41C85 | F 对 E | U056 | F | E | 左较好 | 否 | 否 | 两侧都发现应用把请求重定向到容器内网 IP；左侧先给通用外部 base URL 修复，右侧从历史推定当前仍是 Magento 2，未经本问确认。 |
| P0B1A804219 | F 对 B | U074 | F | B | 右较好 | 否 | 否 | 两侧都解释 Compose 环境替换需外部来源；右侧另给同文件重复静态值可用 YAML 锚点的办法，回应了“同一文件定义”这一需求。 |
| P2F718B9205 | F 对 E | U003 | F | E | 持平 | 否 | 否 | 两侧都正确区分 Dockerfile EXPOSE 与运行时 -p/-P，例子和解释均充分。 |
| PBBC820E6C9 | F 对 B | U048 | B | F | 右较好 | 是 | 否 | 两侧均能指出数据库连接变量缺失；左侧追加无证据的数据库所有权修改，右侧准确解释 psql -U 未指定 -d 时默认找同名数据库，回答了更新中的疑问。 |
| P4FEC8A8C0A | F 对 B | U023 | F | B | 左较好 | 否 | 否 | 两侧都说明 Compose 可自动拉私库镜像；左侧补充认证与 HTTP registry 前提及最小部署命令，较完整但未引入多余部署框架。 |
| PA746809BDA | F 对 E | U038 | E | F | 右较好 | 否 | 否 | 两侧都识别 GitLab 缺 DB_* 变量；右侧准确解释 psql 以用户名作为默认数据库名，左侧额外建议更改数据库所有权与卷结构而缺乏当前问题证据。 |
| P38770CF961 | F 对 B | U022 | F | B | 左较好 | 否 | 是 | 左侧正确指出 ARG 必须保留、Compose 可从 shell 或 .env 做变量替换，并排查 sudo 环境丢失；右侧错误声称 ${VAR} 只读取 .env、不读 shell 环境。 |
| PB97017A4E1 | F 对 B | U051 | B | F | 右较好 | 否 | 否 | 两侧都给出 qcow2 客体安装 docker.io 后清理保存的路径；右侧针对 KVM/OpenStack 的步骤更顺畅，左侧加入不适合 cloud image 的默认登录假设。 |
| P5E65FDF215 | F 对 E | U052 | F | E | 双方关键错误 | 是 | 是 | 两侧都建议 Registrator 容器通过 localhost:8500 访问宿主机 Consul agent，但未给 Registrator host 网络；普通容器的 localhost 指向自身，示例不可直接工作。 |
| P768D6A305F | F 对 E | U060 | F | E | 右较好 | 否 | 否 | 两侧都解释 ENTRYPOINT exec 形式不解释 shell 变量；右侧逐项解释用户三次失败写法并给出 ENV 或 shell 形式，贴合提问。 |
| PCC887BE5AA | F 对 E | U024 | F | E | 右较好 | 是 | 否 | 左侧把递归 nextTick 直接归于 inotify 限额，右侧至少先比较 Node 版本、卷挂载与 watch 任务以定位，仍有推测但方法更稳妥。 |
| PD84E675C8B | F 对 B | U052 | F | B | 双方关键错误 | 是 | 是 | 两侧均建议 Registrator 容器访问 localhost:8500 的宿主机 Consul agent，却没有给 Registrator 配置 host 网络；该地址在普通容器内指向自身，示例无法直接工作。 |
| P7D7A086309 | F 对 E | U019 | E | F | 左较好 | 否 | 否 | 两侧都正确指出 sudo 只作用于管道左侧，左侧先给直接可用的 sudo docker import 修复，再给加用户组方案。 |
| PE3564C9642 | F 对 B | U056 | F | B | 左较好 | 否 | 否 | 两侧都找到重定向到不可达容器 IP 的原因；左侧优先给通用外部 base URL 修复，右侧未经本题确认就当成 Magento 2 处理。 |
| P73D3B36446 | F 对 E | U074 | F | E | 右较好 | 否 | 否 | 两侧都解释 Compose 变量来源；右侧给同文件静态重复值的 YAML 锚点并明确其与变量替换的区别，回应题目细节。 |
| P45B0636042 | F 对 B | U046 | B | F | 右较好 | 是 | 否 | 两侧均解释构建期 RUN 与运行期 -e；左侧额外执行 Magento 安装并把多项凭据硬编码进镜像，偏离需求；右侧保留运行时配置思路。 |
| P522A4B2EE3 | F 对 E | U085 | F | E | 持平 | 否 | 否 | 两侧都正确以 networks.get(name).remove() 删除特定网络，并说明 prune 只清理未使用网络；差别很小。 |
| PDEC963CEBE | F 对 E | U077 | E | F | 左较好 | 否 | 否 | 两侧都列出 minimesos 的 Docker socket、状态目录等排查；左侧优先诊断 CLI 包装器与目录权限，右侧扩展到 SELinux 关闭试验，当前证据不足。 |
| P960CD166CE | F 对 E | U039 | F | E | 双方关键错误 | 是 | 是 | 两侧都把官方 php:5.6-jessie 镜像误当作发行版 PHP 包安装路径；该镜像应检查 docker-php-ext-install bcmath，两个答复的首选命令均不适用。 |
| P500F5DBE7B | F 对 B | U085 | B | F | 持平 | 否 | 否 | 两侧都正确使用 SDK 的 Network.remove 而非 prune；一侧多些说明，没有实质优劣。 |
| P23594F23E1 | F 对 B | U070 | F | B | 左较好 | 否 | 是 | 左侧同时指出 Meteor 容器内监听 3000 与 Mongo 连接失败；右侧无证据断言两个 Compose 服务不在同一网络，且保留错误的 3003:3003 映射。 |
| PFD732EDE44 | F 对 E | U058 | F | E | 右较好 | 否 | 否 | 两侧都给出 Chrome 容器常用启动参数；右侧先改 no-sandbox 与 dev-shm，再检查库依赖，左侧直接整段重装环境。 |
| P7D9C79AA9B | F 对 E | U043 | E | F | 持平 | 否 | 否 | 两侧都正确把宿主机 27018 映射至容器 27017，并说明 RoboMongo 连 localhost:27018；附加排查差别不大。 |
| P99B17C58A6 | F 对 B | U003 | B | F | 持平 | 否 | 否 | 两侧都正确指出 Dockerfile 无 PUBLISH 指令，EXPOSE 是元数据，-p/-P 在运行时发布；价值相当。 |
| P39E51D83C7 | F 对 E | U036 | F | E | 持平 | 否 | 否 | 两侧都识别 Java HttpClient 误用 UrlEncodedFormEntity，需要 JSON StringEntity 与正确 Content-Type；示例只有小的配置差异。 |
| PBC8EC22C6D | F 对 E | U001 | F | E | 持平 | 否 | 否 | 原 YAML 的 db/app 一空格缩进是一致的；两侧均把它说成缩进错误，虽加 version 后示例可用，却没有准确指出版本字段缺失导致格式解析问题。 |
| P5DEB8055EA | F 对 B | U038 | B | F | 右较好 | 否 | 否 | 两侧都识别 sameersbn/gitlab 缺数据库变量；右侧还解释 psql -U 未指定 -d 时为何找同名数据库，覆盖问题更新。 |
| PEBEDABDAAA | F 对 B | U082 | F | B | 右较好 | 否 | 否 | 两侧都指出 MySQL 服务端 max_allowed_packet 仍须增大；右侧先核实当前服务端值及配置是否生效，符合已修改配置却仍报错的场景。 |
| P25046683BB | F 对 B | U026 | B | F | 左较好 | 是 | 是 | 两侧均修正 nginx proxy_pass 为 wiki:3000，但都把脱敏后的 POSTGRES_PASSWORD 与明文 DB_PASS 当作已证实不匹配；左侧先处理 502 主问，右侧提议删除数据库卷风险更高。 |
| P4E83761663 | F 对 E | U028 | F | E | 右较好 | 否 | 否 | 两侧都用运行时 bind mount 放入主机 tests；右侧直接对应题中 /code 工作目录和测试挂载位置，命令更简洁。 |
| PC978F70910 | F 对 B | U033 | B | F | 左较好 | 否 | 是 | 两份 Compose 同时运行时可合并到同一默认网络；左侧移除 hosting 的 network_mode bridge 并用 django 服务名代理，右侧错误要求预建外部网络。 |
| PB0F9BD84F3 | F 对 E | U029 | F | E | 右较好 | 否 | 否 | 两侧都将 Logstash IP 换成 Swarm 服务名；右侧直接指出模板变量应改为服务名，并列明 Filebeat 在 Swarm 外运行时的边界。 |
| PA660ECE7CD | F 对 B | U019 | F | B | 右较好 | 否 | 否 | 两侧都正确指出 sudo 仅作用管道左侧；右侧首先给 sudo docker import 的一行修复，再说明永久用户组设置。 |
| P68FBFFD917 | F 对 E | U035 | E | F | 左较好 | 否 | 否 | 两侧都说明 boot2docker ip 应在 Windows 主机执行；左侧额外提供 VM 内查询 IP 和 Toolbox 命令的条件备选，内容仍紧凑。 |
| P9AD9F2B8DC | F 对 B | U012 | B | F | 左较好 | 否 | 否 | 两侧都正确指出 Windows Server 2016 镜像清单不匹配；左侧优先给 MCR 的 ltsc2016 镜像测试，较贴近 2019 年镜像来源。 |

## 写入论文时的口径

可报告这 40 位用户、80 对回答的团队共识比较及各组计数。对整体画像的增量应按 F 与 E 的直接对照解释；对历史信息整理的作用可结合 F 与 B 以及具体案例讨论。方法部分应交代评分由 AI 起草、作者和同伴审阅并采纳，不表述为两名评阅者独立标注，也不报告未计算的一致性系数。
