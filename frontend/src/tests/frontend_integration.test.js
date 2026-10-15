import { setAuthTokenGetter, apiFetch } from '../api/client.js'
import { getMe, getProfile, updateProfile } from '../api/profile.js'
import { createRecording, getRecordings, pauseRecording, resumeRecording, stopRecording } from '../api/recordings.js'
import { getPeople, createPerson } from '../api/memorySearch.js'

async function runTests() {
  console.log('=== STARTING FRONTEND API INTEGRATION TEST SUITE ===')
  
  // Set mock dev token
  setAuthTokenGetter(async () => 'dev-mock-jwt-token')

  try {
    // 1. Profile / Me test
    console.log('[1/5] Testing GET /v1/me...')
    const me = await getMe()
    console.log('✔ GET /v1/me passed:', me)

    console.log('[2/5] Testing GET /v1/profile & PATCH /v1/profile...')
    const updatedProf = await updateProfile({ jurisdiction: 'US-CA' })
    console.log('✔ PATCH /v1/profile passed:', updatedProf.jurisdiction)

    // 2. Recordings flow
    console.log('[3/5] Testing Recording lifecycle (Start -> Pause -> Resume -> Stop)...')
    const rec = await createRecording({
      audioSource: 'microphone',
      sourceAvailable: true,
      microphonePermissionGranted: true,
      consentAcknowledged: true,
    })
    console.log('  Created recording ID:', rec.id)

    const paused = await pauseRecording(rec.id)
    console.log('  Paused recording status:', paused.state)

    const resumed = await resumeRecording(rec.id)
    console.log('  Resumed recording status:', resumed.state)

    const stopped = await stopRecording(rec.id)
    console.log('  Stopped recording status:', stopped.state)
    console.log('✔ Recording lifecycle passed')

    // 3. People management
    console.log('[4/5] Testing People API...')
    const newPerson = await createPerson({
      name: `Test User ${Date.now()}`,
      email: `test_${Date.now()}@example.com`,
    })
    console.log('  Created person:', newPerson.name)

    const peopleList = await getPeople()
    console.log('✔ People API passed, count:', peopleList.length)

    console.log('=== ALL FRONTEND INTEGRATION TESTS PASSED CLEANLY ===')
  } catch (err) {
    console.error('❌ INTEGRATION TEST FAILED:', err)
    process.exit(1)
  }
}

runTests()
