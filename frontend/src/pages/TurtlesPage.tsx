import { Camera, Edit3, Plus, Ruler, Sun, Thermometer, Trash2, Weight, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Attachment, Turtle } from "../types";

type TurtleForm = Omit<Turtle, "id" | "user_id" | "photo" | "created_at" | "updated_at">;
const emptyForm: TurtleForm = { name: "", species: "", turtle_type: "aquatic", age: "", sex: "unknown", habitat: "", placement: "indoor", enclosure_size: "", has_uvb: false, has_heater: false, diet: "", notes: "" };

export function TurtlesPage() {
  const [turtles, setTurtles] = useState<Turtle[]>([]); const [editing, setEditing] = useState<Turtle | null>(null);
  const [form, setForm] = useState<TurtleForm>(emptyForm); const [modalOpen, setModalOpen] = useState(false);
  const [photo, setPhoto] = useState<File | null>(null); const [error, setError] = useState(""); const [saving, setSaving] = useState(false);
  const load = () => api<Turtle[]>("/turtles").then(setTurtles).catch((err) => setError(err.message));
  useEffect(() => { void load(); }, []);

  function openCreate() { setEditing(null); setForm(emptyForm); setPhoto(null); setError(""); setModalOpen(true); }
  function openEdit(turtle: Turtle) {
    const { id: _id, user_id: _uid, photo: _photo, created_at: _created, updated_at: _updated, ...values } = turtle;
    setEditing(turtle); setForm(values); setPhoto(null); setError(""); setModalOpen(true);
  }
  async function submit(event: FormEvent) {
    event.preventDefault(); setSaving(true); setError("");
    try {
      const turtle = editing
        ? await api<Turtle>(`/turtles/${editing.id}`, { method: "PATCH", body: JSON.stringify(form) })
        : await api<Turtle>("/turtles", { method: "POST", body: JSON.stringify(form) });
      if (photo) {
        const body = new FormData(); body.append("file", photo);
        await api<Attachment>(`/turtles/${turtle.id}/photo`, { method: "POST", body });
      }
      setModalOpen(false); await load();
    } catch (err) { setError(err instanceof Error ? err.message : "儲存失敗。"); }
    finally { setSaving(false); }
  }
  async function remove(turtle: Turtle) {
    if (!window.confirm(`確定刪除 ${turtle.name} 的 Profile 嗎？`)) return;
    await api(`/turtles/${turtle.id}`, { method: "DELETE" }); await load();
  }

  return (
    <div className="page-shell">
      <header className="page-header"><div><span className="header-kicker">Turtle profiles</span><h1>我的龜龜</h1><p>把重要資料記在這裡，AI 每次都能給出更貼近牠的建議。</p></div><button className="primary-button" onClick={openCreate}><Plus size={18} /> 新增龜龜</button></header>
      {error && !modalOpen && <div className="form-error">{error}</div>}
      {turtles.length === 0 ? <div className="empty-state-card"><div className="empty-turtle">龜</div><h2>建立第一份龜龜資料</h2><p>加入物種、環境與設備資訊，讓日後的每次提問更精準。</p><button className="primary-button" onClick={openCreate}><Plus size={18} /> 新增龜龜</button></div> : (
        <div className="turtle-grid">{turtles.map((turtle) => <article className="turtle-card" key={turtle.id}>
          <div className="turtle-photo">{turtle.photo ? <img src={turtle.photo.url ?? `/api/v1/attachments/${turtle.photo.id}`} alt={turtle.name} /> : <span>龜</span>}<div className={`type-pill ${turtle.turtle_type}`}>{turtle.turtle_type === "aquatic" ? "水龜" : "陸龜"}</div></div>
          <div className="turtle-card-body"><div className="turtle-card-title"><div><h2>{turtle.name}</h2><p>{turtle.species}</p></div><div><button className="icon-button" onClick={() => openEdit(turtle)}><Edit3 size={17} /></button><button className="icon-button danger-hover" onClick={() => void remove(turtle)}><Trash2 size={17} /></button></div></div>
          <div className="turtle-facts"><span><Ruler size={16} />{turtle.shell_length_cm ? `${turtle.shell_length_cm} cm` : "未填背甲"}</span><span><Weight size={16} />{turtle.weight_g ? `${turtle.weight_g} g` : "未填體重"}</span><span><Sun size={16} />{turtle.has_uvb ? "有 UVB" : "無 UVB"}</span><span><Thermometer size={16} />{turtle.has_heater ? "有加熱" : "無加熱"}</span></div>
          {turtle.habitat && <p className="habitat-note">{turtle.habitat}</p>}</div>
        </article>)}</div>
      )}

      {modalOpen && <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && setModalOpen(false)}><form className="modal-card turtle-form" onSubmit={submit}>
        <div className="modal-header"><div><span className="form-kicker">{editing ? "編輯 Profile" : "新增 Profile"}</span><h2>{editing ? `更新 ${editing.name}` : "認識你的龜龜"}</h2></div><button type="button" className="icon-button" onClick={() => setModalOpen(false)}><X size={20} /></button></div>
        {error && <div className="form-error">{error}</div>}
        <div className="photo-picker"><label>{photo ? <img src={URL.createObjectURL(photo)} alt="預覽" /> : editing?.photo ? <img src={editing.photo.url ?? `/api/v1/attachments/${editing.photo.id}`} alt={editing.name} /> : <Camera size={24} />}<input type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={(e) => setPhoto(e.target.files?.[0] ?? null)} /></label><div><strong>龜龜照片</strong><span>JPEG、PNG 或 WebP，最多 5 MB</span></div></div>
        <div className="form-grid two"><label>名稱<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label><label>種類<input value={form.species} onChange={(e) => setForm({ ...form, species: e.target.value })} placeholder="例如：臺灣斑龜" required /></label></div>
        <div className="form-grid three"><label>類型<select value={form.turtle_type} onChange={(e) => setForm({ ...form, turtle_type: e.target.value as "aquatic" | "terrestrial" })}><option value="aquatic">水龜</option><option value="terrestrial">陸龜</option></select></label><label>年齡<input value={form.age ?? ""} onChange={(e) => setForm({ ...form, age: e.target.value })} placeholder="例如：約 6 歲" /></label><label>性別<select value={form.sex} onChange={(e) => setForm({ ...form, sex: e.target.value as TurtleForm["sex"] })}><option value="unknown">未知</option><option value="male">公</option><option value="female">母</option></select></label></div>
        <div className="form-grid three"><label>背甲長度（cm）<input type="number" min="0" step="0.1" value={form.shell_length_cm ?? ""} onChange={(e) => setForm({ ...form, shell_length_cm: e.target.value ? Number(e.target.value) : undefined })} /></label><label>體重（g）<input type="number" min="0" step="1" value={form.weight_g ?? ""} onChange={(e) => setForm({ ...form, weight_g: e.target.value ? Number(e.target.value) : undefined })} /></label><label>位置<select value={form.placement ?? "indoor"} onChange={(e) => setForm({ ...form, placement: e.target.value as "indoor" | "outdoor" })}><option value="indoor">室內</option><option value="outdoor">室外</option></select></label></div>
        <div className="form-grid two"><label>飼養箱尺寸<input value={form.enclosure_size ?? ""} onChange={(e) => setForm({ ...form, enclosure_size: e.target.value })} placeholder="例如：120 × 60 × 50 cm" /></label><div className="toggle-group"><label className="check-label"><input type="checkbox" checked={form.has_uvb ?? false} onChange={(e) => setForm({ ...form, has_uvb: e.target.checked })} />有 UVB</label><label className="check-label"><input type="checkbox" checked={form.has_heater ?? false} onChange={(e) => setForm({ ...form, has_heater: e.target.checked })} />有加熱設備</label></div></div>
        <label>飼養環境<textarea value={form.habitat ?? ""} onChange={(e) => setForm({ ...form, habitat: e.target.value })} rows={2} placeholder="水深、底材、過濾、曬背區等" /></label><label>飲食方式<textarea value={form.diet ?? ""} onChange={(e) => setForm({ ...form, diet: e.target.value })} rows={2} /></label><label>備註<textarea value={form.notes ?? ""} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={2} /></label>
        <div className="modal-actions"><button type="button" className="secondary-button" onClick={() => setModalOpen(false)}>取消</button><button className="primary-button" disabled={saving}>{saving ? "儲存中…" : "儲存 Profile"}</button></div>
      </form></div>}
    </div>
  );
}

