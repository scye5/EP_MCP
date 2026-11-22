# 访问 ROSAT 和 eROSITA 档案服务及 HiLIGT 工具

请在 `xray_archive` 目录下、使用 Python 3.10 或更新版本运行以下 Bash 命令。两个客户端都仅使用标准库。查询坐标采用 ICRS 十进制度。命令行搜索半径以度为单位；现有的 MCP 工具 `query_survey` 以角秒为单位。产品下载会先流式写入临时文件，再将完成的文件发布到所请求的路径。请在已有的输出目录中使用新的文件名。

## ROSAT

以下命令暴露了 HEASARC 目录锥形搜索服务、图像发现、DataLink 解析以及同步 TAP。图像服务返回产品链接；解析其中的某个 DataLink URL 可得到相关文件及其语义。对结果中的文件 URL 使用 `download`。`sources` 和 `limit` 命令分别访问 VizieR 和 HiLIGT。[HEASARC 协议指南](https://heasarc.gsfc.nasa.gov/docs/archive/vo/instructions.html)

```bash
python rosat.py cone 83.63 22.01 --radius 1 > crab-cone.xml
python rosat.py images 83.63 22.01 --size 1 > crab-images.xml
python rosat.py datalink 'https://heasarc.gsfc.nasa.gov/xamin/vo/datalink?datalink_key&id=ivo://nasa.heasarc/rosmaster?RH500047N00/rosat.obs_hri.im.im1_fits' > crab-files.xml
python rosat.py tap 'SELECT TOP 1 * FROM rassmaster' > survey-example.xml
python rosat.py sources 83.63 22.01 --radius-arcsec 90
python rosat.py limit 83.63 22.01 --mission RosatPointedHRI --sigma 3
```

通过 TAP/ADQL 搜索观测**中心**。使用 `rosmaster` 表示指向观测，`rassmaster` 表示巡天场。输出是一个保留字段描述和单位的 VOTable。若指向观测搜索的 TAP 连接失败，客户端会转而搜索 NASA 的 PSPC 和 HRI 已处理数据索引，并在 stderr 上报告这一切换。回退 VOTable 包含目标、坐标、序列、曝光和日期。巡天表仍需要 TAP。应选择足够大的搜索半径，以纳入离轴指向，并确认候选体处的曝光。对于源探测，现有的 `archive.query_survey("rosat", ra, dec)` 使用 VizieR 的 2RXS。[HEASARC TAP 指南](https://heasarc.gsfc.nasa.gov/docs/archive/vo/instructions.html)

```bash
python rosat.py observations 83.63 22.01 --table rosmaster --radius 1 > crab-pointings.xml
python rosat.py observations 83.63 22.01 --table rassmaster --radius 4 > crab-survey-fields.xml
```

在选择下载之前，先列出一次观测的实际文件。该示例检索一幅 PSPC 图像，并保留其 Unix 压缩后缀。`--prefix` 还可以浏览 NASA 公共存储桶中的其他 ROSAT 集合和子目录。返回的文件大小以字节为单位。[档案序列](https://heasarc.gsfc.nasa.gov/docs/rosat/archive_access.html) · [HEASARC 云端访问](https://heasarc.gsfc.nasa.gov/docs/archive/cloud.html)

```bash
python rosat.py products --sequence rp500065n00
python rosat.py download 'https://nasa-heasarc.s3.amazonaws.com/rosat/data/pspc/processed_data/500000/rp500065n00/rp500065n00_im1.fits.Z' crab-im1.fits.Z
python rosat.py products --prefix rosat/data/
```

对于跨任务的限制，现有的 `archive.query_hiligt` 接受 `RosatSurvey`、`RosatPointedPSPC` 和 `RosatPointedHRI`。在将限制与 EP 比较之前，请选择显著性水平和能谱模型。HEASARC 还提供交互式的 Browse/Xamin、VO 图像发现、SkyView 图像裁剪以及 Astroquery 方法，用于定位和下载相关产品。[HiLIGT](https://xmmuls.esac.esa.int/upperlimitserver/) · [HEASARC 服务目录](https://heasarc.gsfc.nasa.gov/docs/archive/apis.html)

## eROSITA

官方 eRODat API 参考中的四个操作分别以 `cone`、`limit`、`limits` 和 `tiles` 暴露。使用 `cone --verb 1` 获取最小的目录列集合，`--verb 2` 获取中等输出，或默认的 `--verb 3` 获取全部列。[eRODat API](https://erosita.mpe.mpg.de/erodat/apis/)

使用官方 Simple Cone Search 获取目录行，使用瓦片服务进行产品发现。锥形搜索限制为 5°。支持的目录包括 `DR2_Main`、`DR2_Hard`、`DR1_Main`、`DR1_Hard`、`DR1_Supp` 和 `DR1_Clusters`。瓦片响应包含瓦片编号 (`srvmap`)、覆盖范围和中心。数值瓦片 ID 应格式化为六位数字，保留前导零。[eRODat API 规范](https://erosita.mpe.mpg.de/erodat/apis/)

```bash
python erosita.py cone 194 -5.7 --catalog DR2_Main --radius 0.025 > sources.xml
python erosita.py tiles 194 -5.7
```

对于单个存档产品，请选择发布版本和产品族。该示例列出瓦片 275135 的 DR1 探测产品，并下载其单波段面积曲线。同样的列表命令也可用于诸如 `EXP_010` 和 `UPP_010` 等产品目录（在可用时）。浏览器下载区显示每个瓦片的可用分组。eRODat 还提供了下载篮，以及一个用于较大集合的独立镜像脚本。DR2 目录页面提供整目录下载。[下载区](https://erosita.mpe.mpg.de/erodat/data/download/) · [镜像说明](https://erosita.mpe.mpg.de/dr1/AllSkySurveyData_dr1/mirroring.html) · [DR2 目录访问](https://erosita.mpe.mpg.de/dr2/AllSkySurveyData_dr2/)

```bash
python erosita.py products 275135 DET_010
python erosita.py download 'https://erosita.mpe.mpg.de/erodat/data/download/135/275/DET_010/em01_275135_020_AreaTab1Blik5_c010.fits.gz' tile275135-area.fits.gz
```

对于未编入目录的位置，可通过 GET 请求单个限制，或通过 POST 发送 JSON 数组。批量 API 最多接受 10,000 个位置-波段查询，并保持输入顺序。波段代码是字符串。DR1 支持 `021`（0.2–0.6 keV）、`022`（0.6–2.3）、`023`（2.3–5）、`024`（0.2–2.3）和 `02e`（0.2–5）。DR2 支持 `023` 和 `024`。在报告限制之前，请检查 `de_sky`、曝光和位置标志。在覆盖范围之外，有效响应可能会省略通量字段。通量上限单位为 erg cm⁻² s⁻¹。[API 参数](https://erosita.mpe.mpg.de/erodat/apis/) · [测光与上限](https://erosita.mpe.mpg.de/dr1/AllSkySurveyData_dr1/UpperLimitServer_dr1/)

```bash
python erosita.py limit 194 -5.7 --survey DR2_eRASSc3 --band 024
cat > positions.json <<'JSON'
[{"ra":194,"dec":-5.7,"band":"024","dr_survey":"DR1_eRASS1"},{"ra":194,"dec":-5.7,"band":"024","dr_survey":"DR2_eRASSc3"}]
JSON
python erosita.py limits positions.json
```

## ESA HiLIGT

当你有候选体位置，并希望获取更早测量的通量或定量上限（包括没有目录对应源的位置）时，使用 HiLIGT。每次请求搜索一个任务档案，并返回其可用能段。请使用客户端打印出的精确任务标识符。[ESA HiLIGT 接口与任务覆盖范围](https://xmmuls.esac.esa.int/upperlimitserver/)

```bash
python hiligt.py missions
python hiligt.py query 15.234 5.678 --mission RosatSurvey > rosat-history.json
python hiligt.py query 15.234 5.678 --mission XMMpnt --sigma 3 --blackbody-ev 100 --nh-cm2 3e20
python hiligt.py query 187.2779 2.0524 --mission SwiftXRT --power-law-slope 2
```

默认使用 XMM-Newton 指向观测、三西格玛上限、幂律谱斜率 1.7，以及 3 × 10²⁰ cm⁻² 的吸收柱密度。黑体温度以 eV 输入。默认启用目录；传入 `--no-catalogue` 可请求 ESA 提供的替代方案。JSON `query` 会记录实际发送的参数。

每个观测-波段行都携带其观测 ID、仪器、日期、曝光（秒）和能量边界（keV）。从 `flux` 读取测得的亮度，从 `flux_upper_limit`（erg cm⁻² s⁻¹）读取上限。计数率及其上限以 counts/s 为单位。缺失的测量显示为 null。空的观测列表表示所选档案在该位置未返回观测行。服务错误会以非零状态退出。在与 EP 比较时，应保留每个上限对应的波段、能谱模型、吸收和显著性水平。
