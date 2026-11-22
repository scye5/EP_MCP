# 访问 ROSAT 与 eROSITA 档案服务及 HiLIGT 工具

在 `xray_archive` 目录下，使用 Python 3.10 或更高版本运行以下 Bash 命令。两个客户端均只使用标准库。查询坐标为 ICRS 十进制度。CLI 的搜索半径以度为单位；现有 MCP 工具 `query_survey` 则以角秒为单位。产品下载会流式写入临时文件，并在请求的路径处发布完整文件。请在已存在的输出目录中使用新文件名。

## ROSAT

以下命令暴露 HEASARC 星表锥形搜索（cone）服务、图像发现、DataLink 解析与同步 TAP。图像服务返回产品链接；解析其中一个 DataLink 链接可得到相关文件及其语义。将解析结果中的文件 URL 用于 `download`。`sources` 与 `limit` 命令分别访问 VizieR 与 HiLIGT。[HEASARC 协议指南](https://heasarc.gsfc.nasa.gov/docs/archive/vo/instructions.html)

```bash
python rosat.py cone 83.63 22.01 --radius 1 > crab-cone.xml
python rosat.py images 83.63 22.01 --size 1 > crab-images.xml
python rosat.py datalink 'https://heasarc.gsfc.nasa.gov/xamin/vo/datalink?datalink_key&id=ivo://nasa.heasarc/rosmaster?RH500047N00/rosat.obs_hri.im.im1_fits' > crab-files.xml
python rosat.py tap 'SELECT TOP 1 * FROM rassmaster' > survey-example.xml
python rosat.py sources 83.63 22.01 --radius-arcsec 90
python rosat.py limit 83.63 22.01 --mission RosatPointedHRI --sigma 3
```

通过 TAP/ADQL 搜索观测**中心**。使用 `rosmaster` 查询指向观测，使用 `rassmaster` 查询巡天视场。输出为 VOTable，保留字段描述与单位。若指向搜索的 TAP 连接失败，客户端会搜索 NASA 的 PSPC 与 HRI 已处理数据索引，并在 stderr 上报告切换情况。回退的 VOTable 包含目标、坐标、序列、曝光与日期。巡天表仍需要 TAP。选择足够大的搜索半径以涵盖离轴指向，并在候选体处确认曝光。对于源探测，现有的 `archive.query_survey("rosat", ra, dec)` 使用 VizieR 2RXS。[HEASARC TAP 指南](https://heasarc.gsfc.nasa.gov/docs/archive/vo/instructions.html)

```bash
python rosat.py observations 83.63 22.01 --table rosmaster --radius 1 > crab-pointings.xml
python rosat.py observations 83.63 22.01 --table rassmaster --radius 4 > crab-survey-fields.xml
```

在选择下载前先列出观测的实际文件。示例检索一张 PSPC 图像并保留其 Unix 压缩后缀。`--prefix` 也可浏览公开 NASA 存储桶中的其他 ROSAT 数据集与子目录。返回的文件大小单位为字节。[档案序列](https://heasarc.gsfc.nasa.gov/docs/rosat/archive_access.html) · [HEASARC 云访问](https://heasarc.gsfc.nasa.gov/docs/archive/cloud.html)

```bash
python rosat.py products --sequence rp500065n00
python rosat.py download 'https://nasa-heasarc.s3.amazonaws.com/rosat/data/pspc/processed_data/500000/rp500065n00/rp500065n00_im1.fits.Z' crab-im1.fits.Z
python rosat.py products --prefix rosat/data/
```

对于跨任务上限，现有的 `archive.query_hiligt` 接受 `RosatSurvey`、`RosatPointedPSPC` 与 `RosatPointedHRI`。在与 EP 比较上限前，请先选择显著性水平与光谱模型。HEASARC 还提供交互式 Browse/Xamin、VO 图像发现、SkyView 图像裁剪以及 Astroquery 方法，用于定位与下载相关产品。[HiLIGT](https://xmmuls.esac.esa.int/upperlimitserver/) · [HEASARC 服务目录](https://heasarc.gsfc.nasa.gov/docs/archive/apis.html)

## eROSITA

官方 eRODat API 参考中的四个操作分别暴露为 `cone`、`limit`、`limits` 与 `tiles`。使用 `cone --verb 1` 获取最小的星表列集，`--verb 2` 获取中间输出，或使用默认的 `--verb 3` 获取全部列。[eRODat API](https://erosita.mpe.mpg.de/erodat/apis/)

使用官方的简单锥形搜索（Simple Cone Search）获取星表行，使用天区服务发现产品。锥形搜索上限为 5°。支持的星表为 `DR2_Main`、`DR2_Hard`、`DR1_Main`、`DR1_Hard`、`DR1_Supp` 与 `DR1_Clusters`。天区响应包含天区编号（`srvmap`）、覆盖区与中心。数值型天区 ID 请格式化为六位数字，保留前导零。[eRODat API 规范](https://erosita.mpe.mpg.de/erodat/apis/)

```bash
python erosita.py cone 194 -5.7 --catalog DR2_Main --radius 0.025 > sources.xml
python erosita.py tiles 194 -5.7
```

对于单个已归档产品，请选择发布版本与产品系列。示例列出天区 275135 的 DR1 探测产品，并下载其单能段面积曲线。同一个列出命令也适用于可用的产品目录，如 `EXP_010` 与 `UPP_010`。浏览器下载区会显示每个天区可用的分组。eRODat 还提供下载篮（download basket），以及用于更大数据集的独立镜像脚本。DR2 星表页面提供整表下载。[下载区](https://erosita.mpe.mpg.de/erodat/data/download/) · [镜像说明](https://erosita.mpe.mpg.de/dr1/AllSkySurveyData_dr1/mirroring.html) · [DR2 星表访问](https://erosita.mpe.mpg.de/dr2/AllSkySurveyData_dr2/)

```bash
python erosita.py products 275135 DET_010
python erosita.py download 'https://erosita.mpe.mpg.de/erodat/data/download/135/275/DET_010/em01_275135_020_AreaTab1Blik5_c010.fits.gz' tile275135-area.fits.gz
```

对于未编目的位置，可通过 GET 请求单个上限，或通过 POST 发送 JSON 数组。批量 API 最多接受 10,000 个位置-能段查询，并保持输入顺序。能段代码为字符串。DR1 支持 `021`（0.2–0.6 keV）、`022`（0.6–2.3）、`023`（2.3–5）、`024`（0.2–2.3）与 `02e`（0.2–5）。DR2 支持 `023` 与 `024`。报告上限前请检查 `de_sky`、曝光与位置标志。在覆盖区之外，有效响应可能省略通量字段。通量上限单位为 erg cm⁻² s⁻¹。[API 参数](https://erosita.mpe.mpg.de/erodat/apis/) · [测光与上限](https://erosita.mpe.mpg.de/dr1/AllSkySurveyData_dr1/UpperLimitServer_dr1/)

```bash
python erosita.py limit 194 -5.7 --survey DR2_eRASSc3 --band 024
cat > positions.json <<'JSON'
[{"ra":194,"dec":-5.7,"band":"024","dr_survey":"DR1_eRASS1"},{"ra":194,"dec":-5.7,"band":"024","dr_survey":"DR2_eRASSc3"}]
JSON
python erosita.py limits positions.json
```

## ESA HiLIGT

当你有候选体位置并想获得早先测得的通量或定量上限（包括没有星表对应源的位置）时，使用 HiLIGT。每次请求搜索一个任务档案，并返回其可用的能段。请使用客户端打印出的精确任务标识符。[ESA HiLIGT 接口与任务覆盖](https://xmmuls.esac.esa.int/upperlimitserver/)

```bash
python hiligt.py missions
python hiligt.py query 15.234 5.678 --mission RosatSurvey > rosat-history.json
python hiligt.py query 15.234 5.678 --mission XMMpnt --sigma 3 --blackbody-ev 100 --nh-cm2 3e20
python hiligt.py query 187.2779 2.0524 --mission SwiftXRT --power-law-slope 2
```

默认使用 XMM-Newton 指向观测、三倍西格玛上限、幂律谱指数 1.7，以及吸收柱密度 3 × 10²⁰ cm⁻²。黑体温度以 eV 为单位输入。默认启用星表；传入 `--no-catalogue` 可请求 ESA 提供的替代方案。JSON 的 `query` 会记录实际发送的参数。

每一行观测-能段都带有其观测 ID、仪器、日期、曝光（秒）与能量边界（keV）。从 `flux` 读取实测亮度，从 `flux_upper_limit` 读取上限（erg cm⁻² s⁻¹）。计数率及其上限单位为 counts/s。缺失的测量显示为 null。空的观测列表表示所选档案在此位置没有返回观测行。服务错误会以非零状态退出。在与 EP 比较时，请在每个上限旁一并保留能段、光谱模型、吸收与显著性水平。
