import { useMemo, useState } from 'react';
import './App.css';

const demoPlan = [
  { code: 'CS101', title: 'Foundations', term: 1, credits: 3, status: 'ready' },
  { code: 'MA101', title: 'Calculus I', term: 1, credits: 4, status: 'ready' },
  { code: 'CS201', title: 'Data Structures', term: 2, credits: 3, status: 'blocked' },
];

function App() {
  const [courses, setCourses] = useState(demoPlan);
  const [selected, setSelected] = useState(null);
  const [message, setMessage] = useState('Local changes are checked before they are sent to the server.');
  const terms = useMemo(() => [1, 2, 3, 4], []);

  function move(code, term) {
    setCourses((current) => current.map((course) => (course.code === code ? { ...course, term } : course)));
    setMessage(`${code} moved to term ${term}. Run server validation before saving.`);
  }

  function onKeyDown(event, course) {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault();
      const direction = event.key === 'ArrowRight' ? 1 : -1;
      move(course.code, Math.max(1, Math.min(4, course.term + direction)));
    }
  }

  async function validatePlan() {
    setMessage('Validating this plan with the application service…');
    try {
      const response = await fetch('/api/v1/plans/validate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ assignment: Object.fromEntries(courses.map((course) => [course.code, course.term])) }),
      });
      const payload = await response.json();
      setMessage(response.ok ? (payload.valid ? 'Server validation passed.' : payload.violations.join(' ')) : 'The server could not validate this draft yet.');
    } catch (error) {
      setMessage('The planner is offline. Local edits are preserved in this screen.');
    }
  }

  return (
    <main className="planner-shell">
      <header className="planner-header">
        <div><p className="planner-kicker">Boiler Reviews · planner island</p><h1>Shape a feasible term sequence.</h1><p>Pin a course, move it with the keyboard, and keep every assumption visible before a solver run.</p></div>
        <button className="primary-action" onClick={validatePlan}>Validate plan</button>
      </header>
      <p className="planner-message" role="status">{message}</p>
      <section className="term-grid" aria-label="Multi-term plan">
        {terms.map((term) => (
          <article className="term-column" key={term} onDragOver={(event) => event.preventDefault()} onDrop={(event) => { const code = event.dataTransfer.getData('text/course'); if (code) move(code, term); }}>
            <div className="term-heading"><span>Term {term}</span><span>{courses.filter((course) => course.term === term).reduce((sum, course) => sum + course.credits, 0)} credits</span></div>
            <div className="course-stack">
              {courses.filter((course) => course.term === term).map((course) => (
                <button className={`course-card ${selected === course.code ? 'is-selected' : ''}`} key={course.code} draggable onDragStart={(event) => event.dataTransfer.setData('text/course', course.code)} onClick={() => setSelected(course.code)} onKeyDown={(event) => onKeyDown(event, course)} aria-pressed={selected === course.code}>
                  <span className="course-code">{course.code}</span><strong>{course.title}</strong><span className={`course-status ${course.status}`}>{course.status === 'blocked' ? 'Prerequisite needed' : 'Ready to check'}</span>
                </button>
              ))}
              <div className="drop-hint">Drop a course here</div>
            </div>
          </article>
        ))}
      </section>
      <aside className="planner-notes"><strong>Assumptions</strong><span>Credits are fixed-point catalog units.</span><span>Academic feasibility and preference ranking stay separate.</span><span>Keyboard: select a course, then use ← / → to move it between terms.</span></aside>
    </main>
  );
}

export default App;
