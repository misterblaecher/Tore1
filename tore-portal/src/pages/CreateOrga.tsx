import Layout from '../ui/Layout'

const siteBase = (import.meta.env.VITE_SITE_URL || 'https://app.tore.be').replace(/\/$/, '')

export default function CreateOrga() {
  const handoffUrl = `${siteBase}/forum/structures?creer=1#create-structure`

  return (
    <Layout title="Créer une structure">
      <section style={{ maxWidth: 620, padding: 20, border: '1px solid #444', borderRadius: 10 }}>
        <h2>Créer une structure TORÈ</h2>
        <p>
          La création d’une structure et la gestion de ses membres utilisent votre compte AppUser du Forum.
          Le portail partenaire reste dédié aux opérations et ne crée pas de session structure à votre place.
        </p>
        <a href={handoffUrl}>Ouvrir le Forum pour créer la structure</a>
      </section>
    </Layout>
  )
}
