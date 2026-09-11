# References and scope / 参考项目与借鉴范围

[English home](../README.md) · [中文首页](../README.zh-CN.md)

Reviewed on 2026-09-12. These references inform documentation and distribution structure; Wamoduck dimensions, joint data, and mass properties come from its own supplied model. / 核查日期：2026-09-12。以下项目用于参考文档与文件分发方式，Wamoduck 的尺寸、关节数据和质量属性以自身提供的模型为依据。

## Open Duck Mini

The [main project](https://github.com/apirrone/Open_Duck_Mini) provides entry points for design files, printing, BOM, and assembly, with separate [runtime](https://github.com/apirrone/Open_Duck_Mini_Runtime) and [training](https://github.com/apirrone/Open_Duck_Playground) repositories. Its [print guide](https://github.com/apirrone/Open_Duck_Mini/blob/v2/docs/print_guide.md) connects file names, quantities, and materials; its [assembly guide](https://github.com/apirrone/Open_Duck_Mini/blob/v2/docs/assembly_guide.md) organizes work by subassembly.

[主项目](https://github.com/apirrone/Open_Duck_Mini)为设计文件、打印、BOM 和装配提供统一入口，另有独立的运行与训练仓库。打印指南对应文件名、数量和材料，装配指南按子装配组织内容。

**Adapted here / 本项目采用：** clear file entry points, a component-to-file table, and explicit documentation gaps. Its dimensions, printing parameters, costs, and motion results are not Wamoduck specifications. / 清楚的文件入口、零件与文件对应表，以及明确标注文档缺口。该项目的尺寸、打印参数、成本和运动效果不能作为 Wamoduck 的规格。

## Pollen Robotics Microduck

The official [microduck](https://github.com/pollen-robotics/microduck) repository covers runtime software; [microduck_rl](https://github.com/pollen-robotics/microduck_rl) covers training and simulation models. The [documentation index](https://github.com/pollen-robotics/microduck/blob/main/docs/README.md) and [roadmap](https://github.com/pollen-robotics/microduck/blob/main/docs/project/roadmap.md) help distinguish implemented behavior from work in progress.

官方 [microduck](https://github.com/pollen-robotics/microduck) 仓库以运行软件为主，[microduck_rl](https://github.com/pollen-robotics/microduck_rl)提供训练与仿真模型。文档索引和路线图区分已实现内容与进行中的工作。

**Adapted here / 本项目采用：** separate mechanical, model, and future runtime/training scopes, with validation limits stated alongside model data. Simulation mesh availability is not equivalent to editable manufacturing CAD. / 区分机械、模型和未来运行／训练资料，在模型数据旁说明验证边界。仿真网格的公开不等于同时公开可编辑的制造 CAD。

## Microduck Replica is a separate project / 区分第三方复刻项目

[Microduck Replica](https://github.com/fanhao375/microduck-replica) and its [CAD companion](https://github.com/fanhao375/microduck-replica-cad) are third-party reconstruction resources, not Pollen's official Microduck repositories. The CAD companion illustrates a separate editable-CAD download entry, with named source attribution and licensing.

[Microduck Replica](https://github.com/fanhao375/microduck-replica)及其 [CAD 配套仓库](https://github.com/fanhao375/microduck-replica-cad)属于第三方复刻资料，不是 Pollen 官方 Microduck 仓库。其可编辑 CAD 下载入口、来源署名与许可证说明可作为文件分发方式的补充参考。

No files from these reference repositories are bundled in this package. This statement covers this packaging work; it is not an independent audit of the original CAD's third-party provenance. No affiliation or endorsement is implied. The existing Wamoduck [MIT license](../LICENSE) has been retained; reference-project licenses have not been substituted for it.

本次整理没有从这些参考仓库打包任何文件；这描述的是本次整理行为，不代表已独立审计原始 CAD 的全部第三方来源，也不表示获得参考项目的关联或背书。保留 Wamoduck 原有的 [MIT 许可证](../LICENSE)，没有套用参考项目的许可证。
