import { describe, it, expect } from 'vitest'
import { htmlToModel, modelToHtml, materialize, emptyModel } from './tableGrid'

describe('tableGrid conversion', () => {
  it('round-trips a flat table', () => {
    const html = '<table><tr><th>H1</th><th>H2</th></tr><tr><td>a</td><td>b</td></tr></table>'
    expect(modelToHtml(htmlToModel(html))).toBe(html)
  })

  it('round-trips colspan and rowspan', () => {
    const html = '<table><tr><th colspan="2">Top</th></tr>'
      + '<tr><td rowspan="2">L</td><td>b</td></tr><tr><td>c</td></tr></table>'
    expect(modelToHtml(htmlToModel(html))).toBe(html)
  })

  it('escapes text like the backend serializer', () => {
    const m = emptyModel(1, 1)
    m.cells[0].text = 'a < b & "c"'
    expect(modelToHtml(m)).toBe('<table><tr><td>a &lt; b &amp; &quot;c&quot;</td></tr></table>')
  })

  it('materialize marks covered slots for a colspan', () => {
    const grid = materialize(htmlToModel('<table><tr><td colspan="2">x</td></tr></table>'))
    expect(grid[0][0].kind).toBe('anchor')
    expect(grid[0][1].kind).toBe('covered')
  })

  it('fills ragged rows with empty cells', () => {
    const m = htmlToModel('<table><tr><td>a</td><td>b</td></tr><tr><td>c</td></tr></table>')
    expect(m.rows).toBe(2)
    expect(m.cols).toBe(2)
    expect(m.cells).toHaveLength(4)
  })
})
