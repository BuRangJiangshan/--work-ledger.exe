import { chromium } from 'playwright-core'
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const STAMP = Date.now().toString().slice(-6)
const PORT = 8800 + Math.floor(Math.random() * 150)
const DATA_DIR = path.resolve('..', `data_e2e_run_${STAMP}`)
const MASTER_TITLE = `XX社区邻里纠纷工单-${STAMP}`
const DUP_TITLE = `同一诉求来电重复件-${STAMP}`
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'
const SHOTS = path.resolve('.e2e', 'shots')
fs.mkdirSync(SHOTS, { recursive: true })

const server = spawn(
  'python',
  ['-u', '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(PORT), '--log-level', 'warning'],
  {
    cwd: path.resolve('..', 'backend'),
    env: { ...process.env, APP_DATA_DIR: DATA_DIR },
    stdio: 'ignore',
  },
)

let BASE = `http://127.0.0.1:${PORT}`
async function waitReady() {
  for (let i = 0; i < 80; i += 1) {
    await new Promise((resolve) => setTimeout(resolve, 500))
    try {
      const resp = await fetch(`${BASE}/api/health`)
      if (resp.ok) return
    } catch (_) {
      /* 等待启动 */
    }
  }
  throw new Error('E2E 服务未能启动')
}
await waitReady()

const results = []
const consoleErrors = []
const badApi = []

const browser = await chromium.launch({
  executablePath: CHROME,
  headless: true,
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
})
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true })
const page = await context.newPage()

page.on('console', (msg) => {
  if (msg.type() === 'error') consoleErrors.push(msg.text())
})
page.on('pageerror', (err) => consoleErrors.push('pageerror: ' + err.message))
page.on('response', (resp) => {
  if (resp.url().includes('/api/') && resp.status() >= 400) {
    badApi.push(`${resp.status()} ${resp.url()}`)
  }
})

async function shot(name) {
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true })
}

async function check(name, fn) {
  try {
    await fn()
    results.push(['PASS', name])
    console.log('PASS ' + name)
  } catch (error) {
    results.push(['FAIL', name, String(error.message).slice(0, 400)])
    console.log('FAIL ' + name + ' :: ' + String(error.message).slice(0, 400))
    try {
      await shot('fail-' + name.replace(/[^\w\u4e00-\u9fa5-]/g, '_').slice(0, 40))
    } catch (_) {}
    throw error
  }
}

async function goto(hash) {
  await page.goto(`${BASE}/${hash}`, { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.page-title', { timeout: 30000 })
}

const msg = (text) => page.locator('.el-message').filter({ hasText: text }).first()

async function main() {
  await check('工作台加载', async () => {
    await goto('#/')
    await page.getByRole('heading', { name: '今日工作台' }).waitFor()
    await page.getByText('临期看板').first().waitFor()
    const cards = await page.locator('.stat-card').count()
    if (cards !== 4) throw new Error('统计卡片数量不是 4，实际 ' + cards)
    await shot('01-dashboard')
  })

  await check('登记事项并进入详情', async () => {
    await page.getByRole('button', { name: /快速登记/ }).click()
    await page.waitForURL(/#\/items\/new/)
    await page.getByPlaceholder(/一句话说清楚/).fill(MASTER_TITLE)
    await page.getByPlaceholder(/信访编号/).fill('GD-2026-001')
    await page.getByPlaceholder(/综治中心/).fill('街道综治中心')
    await page.getByRole('button', { name: '保存并查看详情' }).click()
    await page.waitForURL(/#\/items\/\d+/, { timeout: 20000 })
    await page.getByText('办理时间线').first().waitFor()
    const hero = await page.locator('.detail-hero').innerText()
    if (!/SX2026-\d{4}/.test(hero)) throw new Error('详情页未显示事项编号：' + hero.slice(0, 120))
    if (!hero.includes('待处理')) throw new Error('详情页状态不是待处理')
    await shot('02-detail')
  })

  await check('补记汇报与领导批示', async () => {
    await page.getByRole('button', { name: '向领导汇报' }).click()
    const dialog = page.getByRole('dialog').filter({ hasText: '补记过程记录' })
    await dialog.locator('textarea').first().fill('电话向张主任汇报进展及初步调解意见')
    await dialog.locator('.el-checkbox').filter({ hasText: '电话' }).click()
    await dialog.getByPlaceholder('如：张主任').fill('张主任')
    await dialog.getByRole('button', { name: '保存记录' }).click()
    await page.waitForSelector('.el-timeline', { timeout: 10000 })
    await page.getByText('电话向张主任汇报进展').first().waitFor()

    await page.getByRole('button', { name: '领导批示' }).click()
    const dialog2 = page.getByRole('dialog').filter({ hasText: '补记过程记录' })
    await dialog2.locator('textarea').first().fill('领导听取汇报并作出批示')
    await dialog2.getByPlaceholder(/批示原文照记/).fill('先联合司法所调解，调解不成上报街道')
    await dialog2.getByRole('button', { name: '保存记录' }).click()
    await page.getByText('先联合司法所调解').first().waitFor()
  })

  await check('办结并核对状态', async () => {
    await page.getByRole('button', { name: '办结' }).click()
    const dialog = page.getByRole('dialog').filter({ hasText: '补记过程记录' })
    await dialog.locator('textarea').first().fill('双方签订调解协议，事项办结')
    await dialog.locator('.el-form-item').filter({ hasText: '办结方式' }).locator('.el-select').click()
    await page
      .locator('.el-select__popper:visible .el-select-dropdown__item')
      .filter({ hasText: '回单销号' })
      .first()
      .click()
    await dialog.getByRole('button', { name: '保存记录' }).click()
    await page.getByText('已办结').first().waitFor()
    const hero = await page.locator('.detail-hero').innerText()
    if (!hero.includes('已办结')) throw new Error('办结后状态未更新')
    await page.getByText('审计历史', { exact: false }).first().waitFor()
    await shot('03-finished')
  })

  await check('台账搜索、置顶与保存过滤器', async () => {
    await goto('#/items')
    await page.getByPlaceholder(/标题 \/ 编号/).fill(MASTER_TITLE)
    await page.getByRole('button', { name: '查询' }).click()
    const row = page.locator('.el-table__row').filter({ hasText: MASTER_TITLE }).first()
    await row.waitFor()
    await row.getByRole('button', { name: '置顶' }).click()
    await row.getByRole('button', { name: '取消置顶' }).waitFor()

    await page.getByRole('button', { name: '保存当前筛选' }).click()
    const box = page.locator('.el-message-box')
    await box.locator('input').fill('本周综治工单')
    await box.getByRole('button', { name: '确定' }).click()
    await msg('筛选方案已保存').waitFor()
    await shot('04-ledger')
  })

  await check('重复件合并与去重标记', async () => {
    const masterResp = await page.request.get(`${BASE}/api/items`, {
      params: { q: MASTER_TITLE },
    })
    const masterData = await masterResp.json()
    if (!masterData.items.length) throw new Error('未找到主事项')
    const masterNo = masterData.items[0].item_no

    const resp = await page.request.post(`${BASE}/api/items`, {
      data: {
        title: DUP_TITLE,
        category: '群众投诉',
        source_type: '群众来电',
        receive_time: '2026-11-21T10:00',
        due_date: '2026-11-30',
      },
    })
    if (!resp.ok()) throw new Error('创建第二个事项失败：' + resp.status())
    const second = await resp.json()

    await goto('#/items')
    await page.getByPlaceholder(/标题 \/ 编号/).fill(DUP_TITLE)
    await page.getByRole('button', { name: '查询' }).click()
    const row = page.locator('.el-table__row').filter({ hasText: DUP_TITLE }).first()
    await row.waitFor()
    await row.getByRole('button', { name: '合并' }).click()
    const dialog = page.getByRole('dialog').filter({ hasText: '合并重复事项' })
    await dialog.locator('.el-select input').click()
    await page.keyboard.type(masterNo)
    const option = page
      .locator('.el-select__popper:visible .el-select-dropdown__item')
      .filter({ hasText: masterNo })
      .first()
    await option.waitFor({ timeout: 15000 })
    await option.click()
    await dialog.getByRole('button', { name: '确认合并' }).click()
    await msg('已合并到主事项').waitFor()

    await page.getByPlaceholder(/标题 \/ 编号/).fill(MASTER_TITLE)
    await page.getByRole('button', { name: '查询' }).click()
    const masterRow = page.locator('.el-table__row').filter({ hasText: MASTER_TITLE }).first()
    await masterRow.getByText('合并1件').waitFor()

    // 已合并事项默认不出现在台账
    const merged = await page.request.get(`${BASE}/api/items`, { params: { q: DUP_TITLE } })
    const mergedData = await merged.json()
    if (mergedData.total !== 0) throw new Error('已合并事项仍出现在默认台账中')
    const secondId = second.id
    const detailResp = await page.request.get(`${BASE}/api/items/${secondId}`)
    const detail = await detailResp.json()
    if (!detail.merged_into) throw new Error('被合并事项缺少 merged_into 标记')
  })

  await check('每日收尾归档', async () => {
    await goto('#/daily-close')
    await page.getByRole('button', { name: '确认归档并生成日报素材' }).click()
    await msg('今日收尾已归档').waitFor()
    await page.getByText('今日收尾已完成并归档').first().waitFor()

    // 同日重复提交会被拒绝
    const dup = await page.request.post(`${BASE}/api/daily-close`, {
      data: { date: new Date().toLocaleDateString('sv-SE'), status: 'done' },
    })
    if (dup.status() !== 409) throw new Error('同一天重复收尾未返回 409，实际 ' + dup.status())
    await shot('05-daily-close')
  })

  await check('汇报中心生成与导出 Word', async () => {
    await goto('#/reports')
    await page.locator('.report-paper').waitFor({ timeout: 20000 })
    const text = await page.locator('.report-paper').innerText()
    if (!text.includes(MASTER_TITLE)) throw new Error('汇报初稿未包含已登记事项')
    if (!text.includes('信访件及群众诉求办理情况')) throw new Error('汇报初稿缺少模板分类标题')

    const downloadPromise = page.waitForEvent('download', { timeout: 20000 })
    await page.getByRole('button', { name: '导出 Word' }).click()
    const download = await downloadPromise
    if (!download.suggestedFilename().endsWith('.docx')) {
      throw new Error('导出文件名不是 docx：' + download.suggestedFilename())
    }
    await shot('06-report')
  })

  await check('统计视图渲染图表与分列口径', async () => {
    await goto('#/stats')
    await page.getByText('按期办结率').first().waitFor()
    await page.locator('.chart-box canvas').first().waitFor({ timeout: 20000 })
    const canvasCount = await page.locator('.chart-box canvas').count()
    if (canvasCount < 3) throw new Error('图表数量不足：' + canvasCount)
    const body = await page.locator('.page').innerText()
    if (!body.includes('批准延期后办结') || !body.includes('无明确时限办结')) {
      throw new Error('统计分列口径未展示')
    }
    await shot('07-stats')
  })

  await check('全局时间线聚合与事件类型过滤', async () => {
    await goto('#/timeline')
    await page.locator('.el-timeline-item').first().waitFor({ timeout: 15000 })
    const items = await page.locator('.el-timeline-item').count()
    if (items < 3) throw new Error('时间线事件不足：' + items)
    await page.getByText('全部事件', { exact: true }).click()
    await page
      .locator('.el-select__popper:visible .el-select-dropdown__item')
      .filter({ hasText: '领导批示' })
      .first()
      .click()
    await page.keyboard.press('Escape')
    await page.waitForTimeout(600)
    const tags = await page.locator('.el-timeline-item .el-tag').allInnerTexts()
    if (!tags.length || !tags.some((t) => t.includes('领导批示'))) {
      throw new Error('按领导批示过滤后未看到批示事件')
    }
  })

  await check('重复任务规则创建与删除', async () => {
    await goto('#/repeats')
    await page.getByRole('button', { name: '新建规则' }).click()
    const dialog = page.getByRole('dialog').filter({ hasText: '新建重复任务规则' })
    await dialog.getByPlaceholder('如：每周一上传周报台账').fill('每周一上传周报台账')
    await dialog.getByPlaceholder(/办结后回访/).fill('上传周报台账 {date}')
    await dialog.getByRole('button', { name: '保存规则' }).click()
    await msg('规则已创建').waitFor()
    const row = page.locator('.el-table__row').filter({ hasText: '每周一上传周报台账' }).first()
    await row.waitFor()

    await row.getByRole('button', { name: '删除' }).click()
    await page.locator('.el-message-box').getByRole('button', { name: '确定' }).click()
    await msg('已删除').waitFor()
  })

  await check('设置保存并生效到汇报标题', async () => {
    const settingsLoaded = page.waitForResponse(
      (r) => r.url().includes('/api/settings') && r.request().method() === 'GET',
    )
    await goto('#/settings')
    await settingsLoaded
    await page.getByPlaceholder(/用于汇报标题/).fill('测试街道')
    await page.getByRole('button', { name: '保存设置' }).click()
    await msg('设置已保存').waitFor()

    const checkSaved = await page.request.get(`${BASE}/api/settings`)
    const saved = await checkSaved.json()
    if (saved.unit_name !== '测试街道') throw new Error('单位名称未保存到后端：' + saved.unit_name)

    await goto('#/reports')
    await page.locator('.report-paper').waitFor({ timeout: 20000 })
    const title = await page.locator('.report-preview-title').innerText()
    if (!title.includes('测试街道')) throw new Error('单位名称未生效到汇报标题：' + title)
  })

  await check('无前端异常与失败接口', async () => {
    const ignorable = (t) =>
      t.includes('favicon') ||
      t.includes('ResizeObserver') ||
      t.includes('Download the Vue Devtools') ||
      (t.includes('Failed to load resource') && t.includes('404'))
    const errors = consoleErrors.filter((t) => !ignorable(t))
    if (errors.length) throw new Error('控制台错误：' + errors.slice(0, 3).join(' | '))
    if (badApi.length) throw new Error('失败接口：' + badApi.slice(0, 5).join(' | '))
  })
}

try {
  await main()
} catch (error) {
  console.log('ABORTED: ' + String(error.message).slice(0, 300))
}

await browser.close()
server.kill()
await new Promise((resolve) => setTimeout(resolve, 1000))
try {
  fs.rmSync(DATA_DIR, { recursive: true, force: true })
} catch (_) {
  /* 数据目录清理失败不影响结论 */
}

const failed = results.filter((r) => r[0] === 'FAIL')
console.log('\n===== E2E SUMMARY =====')
for (const r of results) console.log(`${r[0]} | ${r[1]}${r[2] ? ' | ' + r[2] : ''}`)
console.log(`TOTAL ${results.length}, FAILED ${failed.length}`)
if (consoleErrors.length) console.log('CONSOLE ERRORS:', consoleErrors.slice(0, 5).join(' | '))
if (badApi.length) console.log('BAD API:', badApi.slice(0, 8).join(' | '))
process.exit(failed.length ? 1 : 0)
